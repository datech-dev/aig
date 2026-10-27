import 'package:flutter/material.dart';
import '../services/analytics_service.dart';

/// Navigation observer that automatically records screen views and transitions.
class AnalyticsNavigatorObserver extends NavigatorObserver {
  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) {
    super.didPush(route, previousRoute);
    _recordRoute(route, previousRoute);
  }

  @override
  void didReplace({Route<dynamic>? newRoute, Route<dynamic>? oldRoute}) {
    super.didReplace(newRoute: newRoute, oldRoute: oldRoute);
    if (newRoute != null) {
      _recordRoute(newRoute, oldRoute);
    }
  }

  void _recordRoute(Route<dynamic> route, Route<dynamic>? previousRoute) {
    final routeName = route.settings.name ?? route.settings.arguments?.toString();
    final prevName = previousRoute?.settings.name;
    
    // Extract screen name
    String screen = 'unknown_screen';
    if (routeName != null && routeName.isNotEmpty) {
      screen = routeName;
    } else {
      // Deduce from route type
      final str = route.toString();
      if (str.contains('ChatScreen')) {
        screen = 'chat_screen';
      } else if (str.contains('StoreScreen')) {
        screen = 'store_screen';
      } else if (str.contains('ProfileScreen')) {
        screen = 'profile_screen';
      } else if (str.contains('MemoriesScreen')) {
        screen = 'memories_screen';
      } else if (str.contains('SettingsScreen')) {
        screen = 'settings_screen';
      } else if (str.contains('OnboardingScreen')) {
        screen = 'onboarding_screen';
      } else if (str.contains('SplashScreen')) {
        screen = 'splash_screen';
      }
    }

    if (screen != 'unknown_screen') {
      analyticsService.logScreenView(screen, fromScreen: prevName);
    }
  }
}
