package com.sentinel.agent

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.LocationManager
import android.provider.CallLog
import android.provider.Telephony
import androidx.core.content.ContextCompat
import org.json.JSONObject
import java.security.MessageDigest

/**
 * Collectors read only from public ContentProviders / LocationManager that the user has
 * explicitly granted at runtime.
 *
 * Child-safety defaults that are baked in, not configurable:
 *  - one-time passcodes are filtered on-device and never transmitted
 *  - only the last known location is read; there is no continuous tracking loop
 */
object Collectors {

    private fun has(ctx: Context, perm: String) =
        ContextCompat.checkSelfPermission(ctx, perm) == PackageManager.PERMISSION_GRANTED

    /** OTP / verification code patterns. Matched messages are dropped before they leave the device. */
    private val OTP_PATTERNS = listOf(
        Regex("(?i)\\b(otp|o\\.t\\.p)\\.?\\b"),
        Regex("(?i)one[- ]?time\\s+(code|passcode|password)"),
        Regex("(?i)verification\\s+code"),
        Regex("(?i)\\b\\d{4,8}\\s+is\\s+your\\s+(code|otp|pin)"),
        Regex("(?i)do\\s+not\\s+share\\s+(this|your)\\s+(code|otp|pin)"),
    )

    fun looksLikeOtp(body: String): Boolean = OTP_PATTERNS.any { it.containsMatchIn(body) }

    fun sms(ctx: Context): List<String> {
        if (!has(ctx, Manifest.permission.READ_SMS)) return emptyList()
        val out = mutableListOf<String>()
        var maxId = Prefs.lastSmsId(ctx)
        val proj = arrayOf(
            Telephony.Sms._ID, Telephony.Sms.ADDRESS, Telephony.Sms.BODY,
            Telephony.Sms.DATE, Telephony.Sms.TYPE
        )
        ctx.contentResolver.query(
            Telephony.Sms.Inbox.CONTENT_URI, proj, "${Telephony.Sms._ID} > ?",
            arrayOf(maxId.toString()), "${Telephony.Sms._ID} ASC LIMIT 100"
        )?.use { c ->
            while (c.moveToNext()) {
                val id = c.getLong(0)
                val addr = c.getString(1) ?: "unknown"
                val body = c.getString(2) ?: ""
                val date = c.getLong(3)
                val type = c.getInt(4)
                if (looksLikeOtp(body)) continue
                out += JSONObject().apply {
                    put("kind", "sms")
                    put("ts", date)
                    put("direction", if (type == Telephony.Sms.MESSAGE_TYPE_INBOX) "in" else "out")
                    put("counterpart", addr)
                    put("body", body)
                }.toString()
                if (id > maxId) maxId = id
            }
        }
        Prefs.setCursors(ctx, maxId, Prefs.lastCallId(ctx))
        return out
    }

    fun calls(ctx: Context): List<String> {
        if (!has(ctx, Manifest.permission.READ_CALL_LOG)) return emptyList()
        val out = mutableListOf<String>()
        var maxId = Prefs.lastCallId(ctx)
        val proj = arrayOf(
            CallLog.Calls._ID, CallLog.Calls.NUMBER, CallLog.Calls.DATE,
            CallLog.Calls.DURATION, CallLog.Calls.TYPE
        )
        ctx.contentResolver.query(
            CallLog.Calls.CONTENT_URI, proj, "${CallLog.Calls._ID} > ?",
            arrayOf(maxId.toString()), "${CallLog.Calls._ID} ASC LIMIT 100"
        )?.use { c ->
            while (c.moveToNext()) {
                val id = c.getLong(0)
                val num = c.getString(1) ?: "unknown"
                val date = c.getLong(2)
                val dur = c.getInt(3)
                val type = c.getInt(4)
                val dir = when (type) {
                    CallLog.Calls.INCOMING_TYPE, CallLog.Calls.MISSED_TYPE -> "in"
                    else -> "out"
                }
                out += JSONObject().apply {
                    put("kind", "call")
                    put("ts", date)
                    put("direction", dir)
                    put("counterpart", num)
                    put("duration", dur)
                    put("payload", JSONObject().put("missed", type == CallLog.Calls.MISSED_TYPE))
                }.toString()
                if (id > maxId) maxId = id
            }
        }
        Prefs.setCursors(ctx, Prefs.lastSmsId(ctx), maxId)
        return out
    }

    fun location(ctx: Context): List<String> {
        val fine = has(ctx, Manifest.permission.ACCESS_FINE_LOCATION)
        val coarse = has(ctx, Manifest.permission.ACCESS_COARSE_LOCATION)
        if (!fine && !coarse) return emptyList()
        val lm = ctx.getSystemService(Context.LOCATION_SERVICE) as LocationManager
        val provider = when {
            fine && lm.isProviderEnabled(LocationManager.GPS_PROVIDER) -> LocationManager.GPS_PROVIDER
            lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER) -> LocationManager.NETWORK_PROVIDER
            else -> null
        } ?: return emptyList()
        val loc = runCatching { lm.getLastKnownLocation(provider) }.getOrNull() ?: return emptyList()
        // Skip re-sending an identical, stale fix every 15 minutes.
        val lastTs = Prefs.lastLocationTs(ctx)
        if (loc.time <= lastTs) return emptyList()
        Prefs.setLastLocationTs(ctx, loc.time)
        return listOf(JSONObject().apply {
            put("kind", "location")
            put("ts", loc.time)
            put("lat", loc.latitude)
            put("lon", loc.longitude)
            put("accuracy", loc.accuracy.toDouble())
            put("payload", JSONObject().put("provider", provider))
        }.toString())
    }

    fun apps(ctx: Context): List<String> {
        val pm = ctx.packageManager
        return pm.getInstalledPackages(0)
            .filter { !it.applicationInfo.sourceDir.startsWith("/system") }
            .map { pkg ->
                JSONObject().apply {
                    put("kind", "app")
                    put("ts", System.currentTimeMillis())
                    put("body", pkg.packageName)
                    put("payload", JSONObject().put("action", "inventory").put("package", pkg.packageName))
                }.toString()
            }
    }

    fun noticeHash(notice: String): String =
        MessageDigest.getInstance("SHA-256").digest(notice.toByteArray())
            .joinToString("") { "%02x".format(it) }.take(32)

    const val CONSENT_NOTICE = """This app shares some information with your parent or guardian.

While it is on, this app records:
  • SMS messages (one-time passcodes are never collected)
  • your call log (number, time, duration)
  • where the phone is (last known position each sync)
  • a list of installed apps

It also shows a permanent notification in your status bar, at all times. Your parent can see it too.
If you press the SOS button, they are alerted immediately.

You can stop this at any time: open Sentinel, tap Stop sharing, and collection ends right away.
Your parent will be told you turned it off."""
}
