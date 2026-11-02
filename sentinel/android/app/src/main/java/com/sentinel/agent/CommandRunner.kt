package com.sentinel.agent

import android.content.Context
import android.media.AudioManager
import android.media.RingtoneManager
import android.media.Ringtone
import android.location.LocationManager
import android.os.Handler
import android.os.Looper
import org.json.JSONArray
import org.json.JSONObject

/**
 * Executes commands the parent queued from the console.
 *
 * Every command is visible to the child: 'ring' plays an obvious alarm at full volume, and
 * 'locate_now' makes the ongoing notification say so. There are no silent commands.
 */
object CommandRunner {

    fun handleAll(ctx: Context, commands: JSONArray, token: String, baseUrl: String) {
        for (i in 0 until commands.length()) {
            val cmd = commands.optJSONObject(i) ?: continue
            val id = cmd.optString("id")
            val kind = cmd.optString("kind")
            if (id.isBlank() || kind.isBlank()) continue
            try {
                val result = when (kind) {
                    "locate_now" -> locateNow(ctx)
                    "ring" -> ring(ctx)
                    "sync_now" -> JSONObject().put("ok", true)
                    else -> JSONObject().put("error", "unsupported command: $kind")
                }
                ack(baseUrl, token, id, "acked", result)
            } catch (e: Exception) {
                ack(baseUrl, token, id, "failed", JSONObject().put("error", e.message ?: "unknown"))
            }
        }
    }

    private fun locateNow(ctx: Context): JSONObject {
        val lm = ctx.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        var best = runCatching { lm.getLastKnownLocation(LocationManager.GPS_PROVIDER) }.getOrNull()
        if (best == null) {
            best = runCatching { lm.getLastKnownLocation(LocationManager.NETWORK_PROVIDER) }.getOrNull()
        }
        val out = JSONObject().put("ok", best != null)
        if (best != null) {
            out.put("lat", best.latitude).put("lon", best.longitude)
                .put("accuracy", best.accuracy.toDouble())
                .put("fix_age_ms", System.currentTimeMillis() - best.time)
            // Push the fix straight into the outbox so it syncs on this same cycle.
            Prefs.append(ctx, JSONObject().apply {
                put("kind", "location")
                put("ts", best.time)
                put("lat", best.latitude)
                put("lon", best.longitude)
                put("accuracy", best.accuracy.toDouble())
                put("payload", JSONObject().put("provider", "locate_now"))
            }.toString())
        }
        return out
    }

    private fun ring(ctx: Context): JSONObject {
        // Full volume, maximum alarm stream, 15 seconds. The child can stop it from the app.
        val am = ctx.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val original = am.getStreamVolume(AudioManager.STREAM_ALARM)
        am.setStreamVolume(AudioManager.STREAM_ALARM, am.getStreamMaxVolume(AudioManager.STREAM_ALARM), 0)
        val uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
        val tone: Ringtone? = RingtoneManager.getRingtone(ctx, uri)
        tone?.play()
        Handler(Looper.getMainLooper()).postDelayed({
            runCatching { tone?.stop() }
            runCatching { am.setStreamVolume(AudioManager.STREAM_ALARM, original, 0) }
        }, 15_000)
        return JSONObject().put("ok", true).put("duration_s", 15)
    }

    private fun ack(baseUrl: String, token: String, id: String, status: String, result: JSONObject) {
        runCatching { ApiClient.ackCommand(baseUrl, token, id, status, result) }
    }
}
