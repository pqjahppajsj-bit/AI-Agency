package com.aiagency.app;

import android.os.Bundle;
import android.graphics.Color;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

public class MainActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setGravity(Gravity.CENTER);
        layout.setPadding(32, 32, 32, 32);
        layout.setBackgroundColor(Color.rgb(248, 250, 252));

        TextView title = new TextView(this);
        title.setText("AI Agency");
        title.setTextSize(32);
        title.setTextColor(Color.rgb(17, 24, 39));
        title.setGravity(Gravity.CENTER);

        TextView subtitle = new TextView(this);
        subtitle.setText(
            "AI-powered business management\\n\\n" +
            "Android app foundation is ready.\\n" +
            "Backend connection comes next."
        );
        subtitle.setTextSize(17);
        subtitle.setTextColor(Color.rgb(107, 114, 128));
        subtitle.setGravity(Gravity.CENTER);
        subtitle.setPadding(0, 24, 0, 0);

        layout.addView(title);
        layout.addView(subtitle);

        setContentView(layout);
    }
}
