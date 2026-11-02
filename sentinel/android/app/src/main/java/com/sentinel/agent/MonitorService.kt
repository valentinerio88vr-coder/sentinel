package com.sentinel.agent

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat

/**
 * Foreground service. Android *requires* the ongoing notification — there is no way to run
 * this silently on a modern OS, and we would not want one. The notification is the user's
 * control surface: it shows status and opens the app to stop monitoring.
 */
class MonitorService : Service() {

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelfAndWipe()
            return START_NOT_STICKY
        }
        startForeground(NOTIF_ID, buildNotification())
        SyncScheduler.schedule(this)
        SyncScheduler.runNow(this)
        return START_STICKY
    }

    private fun stopSelfAndWipe() {
        Prefs.setEnabled(this, false)
        Prefs.wipe(this)
        SyncScheduler.cancel(this)
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
        val n = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        n.cancel(NOTIF_ID)
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val ch = NotificationChannel(
                CHANNEL_ID, "Monitoring active", NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Shown whenever Sentinel is collecting data"
                setShowBadge(false)
            }
            (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(ch)
        }
    }

    private fun buildNotification(): Notification {
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, StatusActivity::class.java), PendingIntent.FLAG_IMMUTABLE
        )
        val stop = PendingIntent.getService(
            this, 1,
            Intent(this, MonitorService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentTitle("Sentinel is sharing with your parent")
            .setContentText("Tap to see what is shared, send SOS, or stop sharing.")
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setContentIntent(open)
            .addAction(0, "Stop sharing", stop)
            .build()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val CHANNEL_ID = "sentinel_monitor"
        const val NOTIF_ID = 4711
        const val ACTION_STOP = "com.sentinel.agent.STOP"

        fun start(ctx: Context) {
            val i = Intent(ctx, MonitorService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) ctx.startForegroundService(i)
            else ctx.startService(i)
        }

        fun stop(ctx: Context) {
            ctx.startService(Intent(ctx, MonitorService::class.java).setAction(ACTION_STOP))
        }
    }
}
