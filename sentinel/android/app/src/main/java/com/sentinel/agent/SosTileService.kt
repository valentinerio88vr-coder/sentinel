package com.sentinel.agent

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import org.json.JSONObject

/**
 * SOS tile in the notification shade — reachable from the lock screen in two taps, which is
 * the point of an SOS. Queues an event durably; it uploads on the next sync even if offline.
 */
class SosTileService : TileService() {

    override fun onStartListening() {
        super.onStartListening()
        qsTile?.apply {
            label = "SOS"
            state = Tile.STATE_INACTIVE
            updateTile()
        }
    }

    override fun onClick() {
        super.onClick()
        trigger(this)
        qsTile?.apply {
            state = Tile.STATE_ACTIVE
            label = "SOS sent"
            updateTile()
        }
    }

    companion object {
        fun trigger(ctx: Context, note: String = "from quick settings") {
            val event = JSONObject().apply {
                put("kind", "sos")
                put("ts", System.currentTimeMillis())
                put("body", note)
            }
            Prefs.append(ctx, event.toString())
            SyncScheduler.runNow(ctx)
        }

        fun intent(ctx: Context): PendingIntent? =
            if (Build.VERSION.SDK_INT >= 24)
                TileService.requestListeningState(ctx, android.content.ComponentName(ctx, SosTileService::class.java))
                    .let { null }
            else null
    }
}
