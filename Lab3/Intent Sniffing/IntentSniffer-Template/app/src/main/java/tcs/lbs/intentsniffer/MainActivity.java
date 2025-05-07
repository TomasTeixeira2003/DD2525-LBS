package tcs.lbs.intentsniffer;

import androidx.appcompat.app.AppCompatActivity;

import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.location.Location;
import android.os.Bundle;
import android.widget.TextView;

import android.content.BroadcastReceiver;

public class MainActivity extends AppCompatActivity
{
    TextView LatitudeTextView, LongitudeTextView;
    //BroadcastActivityReceiver mReceive;


    @Override
    protected void onCreate(Bundle savedInstanceState)
    {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        LatitudeTextView = findViewById(R.id.LatitudeTextView);
        LongitudeTextView = findViewById(R.id.LongitudeTextView);



        // Register to receive broadcast messages from ForegroundLocationService of the LocationApp
        // Register MainActivityReceiver class to listen to broadcasts from ForegroundLocationService
        IntentFilter filter = new IntentFilter();

        //for inter-app communication capturing
        filter.addAction("tcs.lbs.weather_app.WeatherBroadcastReceiver");

        //for intra-app communication capturing
        //filter.addAction("tcs.lbs.locationapp.MainActivityReceiver"); //has to be this because of locationApp->ForegroundLocationService.java line 49

        registerReceiver(new BroadcastActivityReceiver(), filter);
    }

    // Define a broadcast receiver class
    public class BroadcastActivityReceiver extends BroadcastReceiver
    {
        // If a broadcast intent is received, this method will be invoked.
        @Override
        public void onReceive(Context context, Intent intent)
        {
            Location location = intent.getParcelableExtra("Location");
            if (location != null)
            {
                // Extract Location coordinates from the broadcast massage and show them in LatitudeTextView and LongitudeTextView
                LatitudeTextView.setText("Latitude: " + location.getLatitude());
                LongitudeTextView.setText("Longitude: " + location.getLongitude());

            }
        }
    }
}
