import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:firebase_database/firebase_database.dart';

import 'services/notification_service.dart';
import 'screens/home_screen.dart';

@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
  debugPrint("Handling a background message: ${message.messageId}");
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize notifications
  await NotificationService().init();

  try {
    // Initialize Firebase using google-services.json
    await Firebase.initializeApp();
    
    // Set up background messaging
    FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);
    
    // Request permission for iOS/Android
    FirebaseMessaging messaging = FirebaseMessaging.instance;
    await messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );
    
    // Get the FCM token and save it to Realtime Database
    String? token = await messaging.getToken();
    if (token != null) {
      debugPrint("FCM Token: $token");
      DatabaseReference ref = FirebaseDatabase.instance.ref("fcm_tokens");
      await ref.child(token).set(true);
    }

    runApp(const SmartGuardApp());
  } catch (e, stackTrace) {
    debugPrint('Firebase initialization failed: $e');
    debugPrintStack(stackTrace: stackTrace);

    runApp(
      MaterialApp(
        debugShowCheckedModeBanner: false,
        home: Scaffold(
          backgroundColor: const Color(0xFF101216),
          body: Center(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.error_outline, color: Colors.redAccent, size: 64),
                  const SizedBox(height: 16),
                  const Text(
                    'Firebase Initialization Failed',
                    style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    e.toString(),
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.grey, fontSize: 13),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class SmartGuardApp extends StatelessWidget {
  const SmartGuardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SmartGuard Fall Alert',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF101216),
        textTheme: GoogleFonts.interTextTheme(ThemeData.dark().textTheme),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF388BFD),
          secondary: Color(0xFFE74C3C),
          surface: Color(0xFF1C202B),
        ),
      ),
      home: const HomeScreen(),
    );
  }
}
