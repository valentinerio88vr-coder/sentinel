package com.sentinel.agent

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * Restarts the foreground service after a reboot — but only if the device is still opted in.
 * The notification comes back with it, so a reboot never makes monitoring invisible.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        if (Prefs.enabled(context) && Prefs.token(context) != null) {
            MonitorService.start(context)
        }
    }
}
