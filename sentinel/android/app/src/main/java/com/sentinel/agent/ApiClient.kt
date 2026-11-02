package com.sentinel.agent

import android.os.Build
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

/** Thin HTTP client. No third-party deps so the APK stays small and auditable. */
object ApiClient {

    data class EnrollResult(val token: String, val deviceId: String, val label: String)

    private fun post(urlStr: String, body: JSONObject, bearer: String? = null): JSONObject {
        val conn = (URL(urlStr).openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 15000
            readTimeout = 20000
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
            if (bearer != null) setRequestProperty("Authorization", "Bearer $bearer")
        }
        try {
            OutputStreamWriter(conn.outputStream).use { it.write(body.toString()) }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val text = BufferedReader(stream.reader()).readText()
            if (code !in 200..299) throw ApiException(code, extractDetail(text, code))
            return JSONObject(text)
        } finally {
            conn.disconnect()
        }
    }

    private fun extractDetail(text: String, code: Int): String =
        runCatching { JSONObject(text).optString("detail") }.getOrNull()
            ?.takeIf { it.isNotBlank() } ?: "HTTP $code"

    class ApiException(val code: Int, override val message: String) : Exception(message)

    fun claim(baseUrl: String, code: String, noticeHash: String): EnrollResult {
        val body = JSONObject().apply {
            put("code", code.trim().uppercase())
            put("model", "${Build.MANUFACTURER} ${Build.MODEL}")
            put("os_version", "Android ${Build.VERSION.RELEASE} (SDK ${Build.VERSION.SDK_INT})")
            put("app_version", BuildConfig.VERSION_NAME)
            put("consent", JSONObject().apply {
                put("accepted", true)          // the UI will not call this unless the box was ticked
                put("consent_version", "v1")
                put("notice_hash", noticeHash)
            })
        }
        val r = post("$baseUrl/api/enroll/claim", body)
        return EnrollResult(r.getString("device_token"), r.getString("device_id"), r.getString("label"))
    }

    fun sync(baseUrl: String, token: String, events: JSONArray, battery: Int, appVersion: String): SyncResult {
        val body = JSONObject().apply {
            put("events", events)
            put("battery", battery)
            put("app_version", appVersion)
        }
        val r = post("$baseUrl/api/sync", body, token)
        return SyncResult(
            accepted = r.optInt("accepted"),
            alerts = r.optJSONArray("alerts") ?: JSONArray(),
            commands = r.optJSONArray("commands") ?: JSONArray(),
        )
    }

    data class SyncResult(val accepted: Int, val alerts: JSONArray, val commands: JSONArray)

    fun ackCommand(baseUrl: String, token: String, id: String, status: String, result: JSONObject) {
        val body = JSONObject().apply {
            put("command_id", id)
            put("status", status)
            put("result", result)
        }
        post("$baseUrl/api/device/commands/ack", body, token)
    }

    /** Server-side kill switch: if the operator revokes or pauses, the agent stops and tears down. */
    fun config(baseUrl: String, token: String): JSONObject {
        val conn = (URL("$baseUrl/api/device/config").openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 10000
            readTimeout = 10000
            setRequestProperty("Authorization", "Bearer $token")
        }
        try {
            val code = conn.responseCode
            val text = BufferedReader(
                (if (code in 200..299) conn.inputStream else conn.errorStream).reader()
            ).readText()
            if (code !in 200..299) throw ApiException(code, extractDetail(text, code))
            return JSONObject(text)
        } finally {
            conn.disconnect()
        }
    }
}
