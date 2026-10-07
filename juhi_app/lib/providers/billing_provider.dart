import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:razorpay_flutter/razorpay_flutter.dart';
import 'package:url_launcher/url_launcher.dart';
import '../data/api_service.dart';
import '../data/local_storage.dart';
import 'profile_provider.dart';

// ── Billing State ────────────────────────────────────────────────────────────

class BillingState {
  final bool isProcessing;
  final String? activePlanLoading;
  final String? errorMessage;
  final String? successMessage;

  const BillingState({
    this.isProcessing = false,
    this.activePlanLoading,
    this.errorMessage,
    this.successMessage,
  });

  BillingState copyWith({
    bool? isProcessing,
    String? activePlanLoading,
    String? errorMessage,
    String? successMessage,
    bool clearActivePlan = false,
    bool clearError = false,
    bool clearSuccess = false,
  }) {
    return BillingState(
      isProcessing: isProcessing ?? this.isProcessing,
      activePlanLoading:
          clearActivePlan ? null : (activePlanLoading ?? this.activePlanLoading),
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      successMessage:
          clearSuccess ? null : (successMessage ?? this.successMessage),
    );
  }
}

// ── Billing Provider ─────────────────────────────────────────────────────────

final billingProvider =
    StateNotifierProvider<BillingNotifier, BillingState>((ref) {
  return BillingNotifier(ref);
});

class BillingNotifier extends StateNotifier<BillingState> {
  final Ref _ref;
  Razorpay? _razorpay;
  String? _pendingOrderId;
  String? _pendingPlanType;
  void Function(String planType)? _onSuccessCallback;
  void Function(String error)? _onErrorCallback;

  BillingNotifier(this._ref) : super(const BillingState()) {
    _initRazorpay();
  }

  void _initRazorpay() {
    try {
      _razorpay = Razorpay();
      _razorpay?.on(Razorpay.EVENT_PAYMENT_SUCCESS, _handlePaymentSuccess);
      _razorpay?.on(Razorpay.EVENT_PAYMENT_ERROR, _handlePaymentError);
      _razorpay?.on(Razorpay.EVENT_EXTERNAL_WALLET, _handleExternalWallet);
    } catch (e) {
      debugPrint('[BillingNotifier] Razorpay init skipped or failed: $e');
    }
  }

  void setCallbacks({
    void Function(String planType)? onSuccess,
    void Function(String error)? onError,
  }) {
    _onSuccessCallback = onSuccess;
    _onErrorCallback = onError;
  }

  Future<void> purchasePlan({
    required String planType,
    required String planTitle,
    required int amountInr,
  }) async {
    final userId = await LocalStorage.getUserId();
    if (userId == null) {
      state = state.copyWith(
        isProcessing: false,
        clearActivePlan: true,
        errorMessage: 'User not logged in. Please restart the app.',
      );
      _onErrorCallback?.call('User not logged in. Please restart the app.');
      return;
    }

    state = state.copyWith(
      isProcessing: true,
      activePlanLoading: planType,
      clearError: true,
      clearSuccess: true,
    );

    _pendingPlanType = planType;
    final amountPaise = amountInr * 100;

    try {
      final orderData = await apiService.createOrder(
        userId: userId,
        planType: planType,
        amountPaise: amountPaise,
      );

      final orderId = orderData['order_id']?.toString() ?? '';
      _pendingOrderId = orderId;
      final gateway = orderData['gateway']?.toString() ?? 'razorpay';
      final rzpKey = orderData['key']?.toString() ?? '';
      final payUrl = orderData['pay_url']?.toString();

      // If Instamojo / Web Gateway URL provided
      if (gateway == 'instamojo' || (payUrl != null && payUrl.isNotEmpty)) {
        state = state.copyWith(isProcessing: false, clearActivePlan: true);
        if (payUrl != null) {
          final uri = Uri.parse(payUrl);
          if (await canLaunchUrl(uri)) {
            await launchUrl(uri, mode: LaunchMode.externalApplication);
          } else {
            throw Exception('Could not open payment link.');
          }
        }
        return;
      }

      // Razorpay Native Checkout
      if (_razorpay == null) {
        _initRazorpay();
      }

      if (_razorpay == null || rzpKey.isEmpty) {
        throw Exception(
            'Razorpay checkout is unavailable. Key or SDK not ready.');
      }

      final options = {
        'key': rzpKey,
        'amount': amountPaise,
        'name': 'Juhi AI Companion',
        'description': planTitle,
        'order_id': orderId,
        'prefill': {
          'contact': '',
          'email': '',
        },
        'theme': {
          'color': '#FF2D7F',
        },
        'retry': {
          'enabled': true,
          'max_count': 1,
        },
      };

      _razorpay!.open(options);
    } catch (e) {
      debugPrint('[BillingNotifier] Error initiating purchase: $e');
      final errorMsg = e.toString().replaceAll('Exception: ', '');
      state = state.copyWith(
        isProcessing: false,
        clearActivePlan: true,
        errorMessage: errorMsg,
      );
      _onErrorCallback?.call(errorMsg);
    }
  }

  Future<void> _handlePaymentSuccess(PaymentSuccessResponse response) async {
    debugPrint(
        '[BillingNotifier] Payment success: order=${response.orderId}, payment=${response.paymentId}');

    final userId = await LocalStorage.getUserId();
    final planType = _pendingPlanType ?? 'chat_pass_1day';
    final orderId = response.orderId ?? _pendingOrderId ?? '';
    final paymentId = response.paymentId ?? '';
    final signature = response.signature ?? '';

    try {
      if (userId != null) {
        await apiService.verifyPayment(
          userId: userId,
          orderId: orderId,
          paymentId: paymentId,
          signature: signature,
          planType: planType,
        );
      }

      // Refresh profile so updated subscription / image credits reflect immediately
      await _ref.read(profileProvider.notifier).refresh();

      final successMsg = _getSuccessMessage(planType);
      state = state.copyWith(
        isProcessing: false,
        clearActivePlan: true,
        successMessage: successMsg,
        clearError: true,
      );

      _onSuccessCallback?.call(planType);
    } catch (e) {
      debugPrint('[BillingNotifier] Verification error: $e');
      final err = 'Payment received but verification had an issue. Refreshing profile...';
      state = state.copyWith(
        isProcessing: false,
        clearActivePlan: true,
        errorMessage: err,
      );
      // Still refresh profile in case backend recorded it via webhook
      await _ref.read(profileProvider.notifier).refresh();
      _onErrorCallback?.call(err);
    } finally {
      _pendingOrderId = null;
      _pendingPlanType = null;
    }
  }

  void _handlePaymentError(PaymentFailureResponse response) {
    debugPrint(
        '[BillingNotifier] Payment failed: code=${response.code}, message=${response.message}');
    final msg = response.message ?? 'Payment was cancelled or failed.';
    state = state.copyWith(
      isProcessing: false,
      clearActivePlan: true,
      errorMessage: msg,
    );
    _onErrorCallback?.call(msg);
    _pendingOrderId = null;
    _pendingPlanType = null;
  }

  void _handleExternalWallet(ExternalWalletResponse response) {
    debugPrint('[BillingNotifier] External wallet: ${response.walletName}');
  }

  String _getSuccessMessage(String planType) {
    switch (planType) {
      case 'chat_pass_1day':
        return '1 Day Unlimited Chat activated! 💕';
      case 'chat_pass_1week':
        return '1 Week VIP Pass activated! 🔥 Enjoy unlimited chats!';
      case 'chat_pass_1month':
        return '1 Month Soulmate Pass activated! 👑 All premium features unlocked!';
      case 'image_credits':
        return '10 Image Credits added! 🎨 Ask Juhi for selfies anytime!';
      default:
        return 'Payment verified! Thank you for supporting Juhi! 💖';
    }
  }

  void clearMessages() {
    state = state.copyWith(clearError: true, clearSuccess: true);
  }

  @override
  void dispose() {
    try {
      _razorpay?.clear();
    } catch (_) {}
    super.dispose();
  }
}
