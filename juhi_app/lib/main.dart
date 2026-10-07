import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'app.dart';
import 'core/router.dart';
import 'services/notification_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Lock to portrait orientation
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // Set system UI overlay style
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: Color(0xFF0A0010),
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );

  // Initialize local notifications
  try {
    await notificationService.initialize(
      onNotificationTap: (payload) {
        if (payload != null && payload.isNotEmpty) {
          rootNavigatorKey.currentContext?.go(payload);
        }
      },
    );
  } catch (e) {
    debugPrint('[Main] Notification initialization error: $e');
  }

  runApp(
    const ProviderScope(
      child: JuhiApp(),
    ),
  );
}
