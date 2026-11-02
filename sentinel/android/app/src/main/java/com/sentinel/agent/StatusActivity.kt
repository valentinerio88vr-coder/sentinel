package com.sentinel.agent

import android.content.Intent
import android.os.Bundle
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import java.text.SimpleDateFormat
import java.util.*

/**
 * Transparency screen. Shows the person carrying the phone exactly what is being sent
 * and gives a one-tap stop. Required by design, not optional.
 */
class StatusActivity : AppCompatActivity() {

    private lateinit var body: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val pad = (16 * resources.displayMetrics.density).toInt()
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad * 2, pad, pad)
        }

        root.addView(TextView(this).apply { text = "Monitoring status"; textSize = 22f })

        body = TextView(this).apply {
            textSize = 13f
            setPadding(0, pad / 2, 0, pad)
        }
        val scroll = ScrollView(this).apply {
            layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f)
        }
        scroll.addView(body)
        root.addView(scroll)

        val sos = Button(this).apply {
            text = "SOS — alert my parent now"
            setBackgroundColor(0xFFDC2626.toInt())
            setTextColor(0xFFFFFFFF.toInt())
        }
        root.addView(sos)

        val stop = Button(this).apply { text = "Stop sharing" }
        root.addView(stop)
        setContentView(root)

        sos.setOnClickListener {
            val km = getSystemService(KEYGUARD_SERVICE) as android.app.KeyguardManager
            val locked = km.isKeyguardLocked
            AlertDialog.Builder(this)
                .setTitle("Send SOS?")
                .setMessage("Your parent or guardian will be alerted immediately with your current location." +
                    if (locked) "\n\nYou can also do this from the SOS tile in quick settings without unlocking." else "")
                .setPositiveButton("Send SOS") { _, _ ->
                    SosTileService.trigger(this, if (locked) "from lock screen" else "from app")
                    body.text = "SOS sent. Your parent has been alerted."
                }
                .setNegativeButton("Cancel", null)
                .show()
        }

        stop.setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle("Stop monitoring?")
                .setMessage("Collection stops immediately, pending data is discarded, and this device's token is deleted. " +
                    "The administrator will see the device as inactive.")
                .setPositiveButton("Stop") { _, _ ->
                    MonitorService.stop(this)
                    startActivity(Intent(this, EnrollActivity::class.java))
                    finish()
                }
                .setNegativeButton("Cancel", null)
                .show()
        }

        refresh()
    }

    override fun onResume() { super.onResume(); refresh() }

    private fun refresh() {
        val enabled = Prefs.enabled(this)
        if (enabled) MonitorService.start(this)
        val outbox = Prefs.outbox(this).lines().count { it.isNotBlank() }
        val fmt = SimpleDateFormat("d MMM yyyy, HH:mm", Locale.getDefault())
        val last = Prefs.lastSync(this).takeIf { it > 0 }?.let { fmt.format(Date(it)) } ?: "not yet"

        body.text = buildString {
            append("Status: ")
            append(if (enabled) "ACTIVE — collecting and syncing" else "STOPPED")
            append("\n\nDevice: ").append(Prefs.label(this@StatusActivity).ifBlank { "—" })
            append("\nServer: ").append(Prefs.baseUrl(this@StatusActivity))
            append("\nLast successful sync: ").append(last)
            append("\nRecords waiting to upload: ").append(outbox)
            append("\n\nWhat is collected\n")
            append("• SMS messages — one-time passcodes are filtered out and never sent\n")
            append("• Call log — number, time, duration\n")
            append("• Last known location at each sync\n")
            append("• List of installed apps\n")
            append("\nWhat is NOT collected\n")
            append("• Message content from WhatsApp/Telegram/Signal or any other app\n")
            append("• Photos, files, keystrokes, screenshots\n")
            append("• Microphone, camera, or screen recording\n")
            append("• Passwords or banking credentials\n")
            append("\nA permanent notification stays in your status bar while this is active.")
        }
    }
}
