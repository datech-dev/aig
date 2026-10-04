class ApiConfig {
  // Production VPS REST API server URL (157.66.191.104:8080)
  static String baseUrl = 'http://157.66.191.104:8080';

  // Endpoints
  static String get authUrl => '$baseUrl/api/auth';
  static String get profileUrl => '$baseUrl/api/profile';
  static String get historyUrl => '$baseUrl/api/history';
  static String get chatUrl => '$baseUrl/api/chat';
  static String get toggleModeUrl => '$baseUrl/api/mode/toggle';
  static String get memoriesUrl => '$baseUrl/api/memories';
}
