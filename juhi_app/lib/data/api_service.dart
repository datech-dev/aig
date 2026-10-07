import 'package:dio/dio.dart';
import '../core/constants.dart';

class ApiService {
  late final Dio _dio;

  ApiService() {
    _dio = Dio(
      BaseOptions(
        baseUrl: AppConstants.baseUrl,
        connectTimeout: const Duration(seconds: 30),
        receiveTimeout: const Duration(seconds: 60),
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ),
    );

    // Add logging interceptor in debug
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          // ignore: avoid_print
          print('[API] ${options.method} ${options.path}');
          handler.next(options);
        },
        onResponse: (response, handler) {
          // ignore: avoid_print
          print('[API] ${response.statusCode} ${response.requestOptions.path}');
          handler.next(response);
        },
        onError: (error, handler) {
          // ignore: avoid_print
          print('[API ERR] ${error.message}');
          handler.next(error);
        },
      ),
    );
  }

  // ── Auth ──────────────────────────────────────────────────────────────────
  Future<Map<String, dynamic>> auth({
    required String userId,
    String username = 'app_user',
    String firstName = 'User',
  }) async {
    final response = await _dio.post(
      AppConstants.apiAuth,
      data: {
        'user_id': userId,
        'username': username,
        'first_name': firstName,
      },
    );
    return response.data as Map<String, dynamic>;
  }

  // ── Profile ───────────────────────────────────────────────────────────────
  Future<Map<String, dynamic>> getProfile(String userId) async {
    final response = await _dio.get(
      AppConstants.apiProfile,
      queryParameters: {'user_id': userId},
    );
    return response.data as Map<String, dynamic>;
  }

  // ── Chat History ──────────────────────────────────────────────────────────
  Future<Map<String, dynamic>> getChatHistory(String userId) async {
    final response = await _dio.get(
      AppConstants.apiHistory,
      queryParameters: {'user_id': userId},
    );
    return response.data as Map<String, dynamic>;
  }

  // ── Send Message ──────────────────────────────────────────────────────────
  Future<Map<String, dynamic>> sendMessage({
    required String userId,
    required String message,
  }) async {
    final response = await _dio.post(
      AppConstants.apiChat,
      data: {
        'user_id': userId,
        'message': message,
      },
    );
    return response.data as Map<String, dynamic>;
  }

  // ── Toggle Mode ───────────────────────────────────────────────────────────
  Future<Map<String, dynamic>> toggleMode(String userId) async {
    final response = await _dio.post(
      AppConstants.apiToggleMode,
      data: {'user_id': userId},
    );
    return response.data as Map<String, dynamic>;
  }

  // ── Memories ──────────────────────────────────────────────────────────────
  Future<Map<String, dynamic>> getMemories(String userId) async {
    final response = await _dio.get(
      AppConstants.apiMemories,
      queryParameters: {'user_id': userId},
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> clearMemories(String userId) async {
    final response = await _dio.post(
      AppConstants.apiMemories,
      data: {'user_id': userId, 'action': 'clear'},
    );
    return response.data as Map<String, dynamic>;
  }

  // ── Payments ──────────────────────────────────────────────────────────────
  Future<Map<String, dynamic>> createOrder({
    required String userId,
    required String planType,
    required int amountPaise,
  }) async {
    final response = await _dio.post(
      AppConstants.apiCreateOrder,
      data: {
        'user_id': userId,
        'item_type': planType,
        'plan_type': planType,
        'amount': amountPaise,
      },
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> verifyPayment({
    required String userId,
    required String orderId,
    required String paymentId,
    required String signature,
    required String planType,
  }) async {
    final response = await _dio.post(
      AppConstants.apiVerifyPayment,
      data: {
        'user_id': userId,
        'order_id': orderId,
        'razorpay_order_id': orderId,
        'payment_id': paymentId,
        'razorpay_payment_id': paymentId,
        'signature': signature,
        'razorpay_signature': signature,
        'item_type': planType,
        'plan_type': planType,
      },
    );
    return response.data as Map<String, dynamic>;
  }

  // ── Notifications ────────────────────────────────────────────────────────
  Future<Map<String, dynamic>> updateDeviceToken({
    required String userId,
    required String deviceToken,
    bool enabled = true,
  }) async {
    final response = await _dio.post(
      AppConstants.apiDeviceToken,
      data: {
        'user_id': userId,
        'device_token': deviceToken,
        'enabled': enabled,
      },
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> requestTestNotification(String userId) async {
    final response = await _dio.post(
      AppConstants.apiTestNotification,
      data: {'user_id': userId},
    );
    return response.data as Map<String, dynamic>;
  }
}

// Singleton instance
final apiService = ApiService();
