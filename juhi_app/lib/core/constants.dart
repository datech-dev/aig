// Core design constants & configuration for Juhi AI Companion

class AppConstants {
  // ── API ───────────────────────────────────────────────────────────────────
  // Change this to your VPS URL (without trailing slash)
  static const String baseUrl = 'https://zetagirl.zetalink.cloud';

  static const String apiAuth = '/api/auth';
  static const String apiProfile = '/api/profile';
  static const String apiHistory = '/api/history';
  static const String apiChat = '/api/chat';
  static const String apiToggleMode = '/api/mode/toggle';
  static const String apiMemories = '/api/memories';
  static const String apiCreateOrder = '/api/create-order';
  static const String apiVerifyPayment = '/api/verify-payment';
  static const String apiConfig = '/api/config';
  static const String apiDeviceToken = '/api/device-token';
  static const String apiTestNotification = '/api/notifications/test';

  // ── Storage Keys ──────────────────────────────────────────────────────────
  static const String keyUserId = 'user_id';
  static const String keyUserName = 'user_name';
  static const String keyOnboardingDone = 'onboarding_done';

  // ── Palette ───────────────────────────────────────────────────────────────
  static const int colorPrimary = 0xFFFF2D7F;
  static const int colorSecondary = 0xFF9B5DE5;
  static const int colorBackground = 0xFF0A0010;
  static const int colorSurface = 0xFF150025;
  static const int colorCard = 0xFF1E0035;
  static const int colorTextPrimary = 0xFFFFFFFF;
  static const int colorTextSecondary = 0xFFC8A9E0;
  static const int colorAccentGold = 0xFFFFD700;
  static const int colorBorder = 0xFF3D1060;

  // ── Relationship Levels ──────────────────────────────────────────────────
  static const List<Map<String, dynamic>> relationshipLevels = [
    {'level': 1, 'title': 'Acquaintances', 'affection': 0, 'xp': 0, 'emoji': '👋'},
    {'level': 2, 'title': 'Friends', 'affection': 100, 'xp': 100, 'emoji': '😊'},
    {'level': 3, 'title': 'Close Friends', 'affection': 300, 'xp': 300, 'emoji': '🤗'},
    {'level': 4, 'title': 'Crushing', 'affection': 600, 'xp': 600, 'emoji': '😍'},
    {'level': 5, 'title': 'Sweethearts', 'affection': 1000, 'xp': 1000, 'emoji': '💕'},
    {'level': 6, 'title': 'Soulmates', 'affection': 1500, 'xp': 1500, 'emoji': '💞'},
  ];

  // ── Pricing ───────────────────────────────────────────────────────────────
  static const int price1Day = 49;
  static const int price1Week = 199;
  static const int price1Month = 499;
  static const int priceImages = 49;

  // ── App Info ──────────────────────────────────────────────────────────────
  static const String appName = 'Juhi';
  static const String appTagline = 'Your AI Companion';
  static const String partnerName = 'Juhi';
}
