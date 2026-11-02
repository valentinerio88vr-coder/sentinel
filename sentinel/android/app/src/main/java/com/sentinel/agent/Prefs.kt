package com.sentinel.agent

import android.content.Context
import android.content.SharedPreferences

/** Local persisted state: enrollment credentials + a durable outbox so nothing is lost offline. */
object Prefs {
    private const val FILE = "sentinel_prefs"
    private fun sp(c: Context): SharedPreferences = c.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    private const val K_TOKEN = "device_token"
    private const val K_DEVICE_ID = "device_id"
    private const val K_LABEL = "label"
    private const val K_BASE_URL = "base_url"
    private const val K_ENABLED = "monitoring_enabled"
    private const val K_LAST_SYNC = "last_sync"
    private const val K_LAST_SMS_ID = "last_sms_id"
    private const val K_LAST_CALL_ID = "last_call_id"
    private const val K_OUTBOX = "outbox"
    private const val K_LAST_LOC_TS = "last_location_ts"

    fun token(c: Context) = sp(c).getString(K_TOKEN, null)
    fun deviceId(c: Context) = sp(c).getString(K_DEVICE_ID, null)
    fun label(c: Context) = sp(c).getString(K_LABEL, "")
    fun baseUrl(c: Context) = sp(c).getString(K_BASE_URL, "")!!
    fun enabled(c: Context) = sp(c).getBoolean(K_ENABLED, false)

    fun saveEnrollment(c: Context, token: String, deviceId: String, label: String, baseUrl: String) {
        sp(c).edit()
            .putString(K_TOKEN, token)
            .putString(K_DEVICE_ID, deviceId)
            .putString(K_LABEL, label)
            .putString(K_BASE_URL, baseUrl)
            .putBoolean(K_ENABLED, true)
            .apply()
    }

    fun setEnabled(c: Context, on: Boolean) = sp(c).edit().putBoolean(K_ENABLED, on).apply()
    fun lastSync(c: Context) = sp(c).getLong(K_LAST_SYNC, 0L)
    fun setLastSync(c: Context, v: Long) = sp(c).edit().putLong(K_LAST_SYNC, v).apply()

    fun lastSmsId(c: Context) = sp(c).getLong(K_LAST_SMS_ID, 0L)
    fun lastCallId(c: Context) = sp(c).getLong(K_LAST_CALL_ID, 0L)
    fun setCursors(c: Context, smsId: Long, callId: Long) {
        sp(c).edit().putLong(K_LAST_SMS_ID, smsId).putLong(K_LAST_CALL_ID, callId).apply()
    }

    /** Outbox is newline-delimited JSON; appended under a lock by the collectors. */
    fun lastLocationTs(c: Context) = sp(c).getLong(K_LAST_LOC_TS, 0L)
    fun setLastLocationTs(c: Context, v: Long) = sp(c).edit().putLong(K_LAST_LOC_TS, v).apply()

    fun outbox(c: Context): String = sp(c).getString(K_OUTBOX, "") ?: ""
    fun writeOutbox(c: Context, s: String) = sp(c).edit().putString(K_OUTBOX, s).apply()

    @Synchronized
    fun append(c: Context, json: String) {
        val cur = outbox(c)
        // Hard cap so a long offline period cannot exhaust storage.
        val lines = (cur + json + "\n").lines().filter { it.isNotBlank() }
        val capped = if (lines.size > 5000) lines.takeLast(5000) else lines
        writeOutbox(c, capped.joinToString("\n", postfix = if (capped.isEmpty()) "" else "\n"))
    }

    fun clearOutbox(c: Context) = sp(c).edit().remove(K_OUTBOX).apply()

    fun wipe(c: Context) = sp(c).edit().clear().apply()
}
