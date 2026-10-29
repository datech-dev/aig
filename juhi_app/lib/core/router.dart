import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../screens/splash/splash_screen.dart';
import '../screens/onboarding/onboarding_screen.dart';
import '../screens/auth/login_screen.dart';
import '../screens/chat/chat_screen.dart';
import '../screens/profile/profile_screen.dart';
import '../screens/store/store_screen.dart';
import '../screens/memories/memories_screen.dart';
import '../screens/settings/settings_screen.dart';
import '../screens/voice_call/voice_call_screen.dart';
import '../widgets/main_shell.dart';
import 'analytics_navigator_observer.dart';

final GlobalKey<NavigatorState> rootNavigatorKey = GlobalKey<NavigatorState>();

final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authStateProvider);

  return GoRouter(
    navigatorKey: rootNavigatorKey,
    initialLocation: '/splash',
    observers: [AnalyticsNavigatorObserver()],
    redirect: (context, state) {
      final isLoading = authState.isLoading;
      final isLoggedIn = authState.valueOrNull ?? false;
      final location = state.uri.toString();

      if (isLoading) return null;

      // Not logged in → go to login/onboarding
      if (!isLoggedIn &&
          location != '/login' &&
          location != '/onboarding' &&
          location != '/splash') {
        return '/login';
      }

      // Logged in → skip splash, onboarding, login
      if (isLoggedIn &&
          (location == '/splash' || location == '/onboarding' || location == '/login')) {
        return '/chat';
      }

      return null;
    },
    routes: [
      GoRoute(
        name: 'splash',
        path: '/splash',
        builder: (context, state) => const SplashScreen(),
      ),
      GoRoute(
        name: 'onboarding',
        path: '/onboarding',
        builder: (context, state) => const OnboardingScreen(),
      ),
      GoRoute(
        name: 'login',
        path: '/login',
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        name: 'call',
        path: '/call',
        parentNavigatorKey: rootNavigatorKey,
        builder: (context, state) => const VoiceCallScreen(),
      ),
      ShellRoute(
        builder: (context, state, child) => MainShell(child: child),
        routes: [
          GoRoute(
            name: 'chat',
            path: '/chat',
            builder: (context, state) => const ChatScreen(),
          ),
          GoRoute(
            name: 'profile',
            path: '/profile',
            builder: (context, state) => const ProfileScreen(),
          ),
          GoRoute(
            name: 'store',
            path: '/store',
            builder: (context, state) => const StoreScreen(),
          ),
          GoRoute(
            name: 'memories',
            path: '/memories',
            builder: (context, state) => const MemoriesScreen(),
          ),
          GoRoute(
            name: 'settings',
            path: '/settings',
            builder: (context, state) => const SettingsScreen(),
          ),
        ],
      ),
    ],
  );
});
