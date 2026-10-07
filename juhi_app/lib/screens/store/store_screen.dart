import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme.dart';
import '../../core/constants.dart';
import '../../providers/billing_provider.dart';
import '../../providers/profile_provider.dart';

class StoreScreen extends ConsumerStatefulWidget {
  const StoreScreen({super.key});

  @override
  ConsumerState<StoreScreen> createState() => _StoreScreenState();
}

class _StoreScreenState extends ConsumerState<StoreScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(billingProvider.notifier).setCallbacks(
            onSuccess: _onPaymentSuccess,
            onError: _onPaymentError,
          );
    });
  }

  void _onPaymentSuccess(String planType) {
    if (!mounted) return;
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (ctx) => _PurchaseCelebrationSheet(planType: planType),
    );
  }

  void _onPaymentError(String error) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.error_outline_rounded,
                color: Color(0xFFFF6B6B), size: 20),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                error,
                style: const TextStyle(color: Colors.white, fontSize: 13),
              ),
            ),
          ],
        ),
        backgroundColor: AppTheme.card,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: Color(0xFFFF6B6B), width: 0.8),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final profileAsync = ref.watch(profileProvider);
    final billingState = ref.watch(billingProvider);

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppTheme.backgroundGradient),
        child: SafeArea(
          child: RefreshIndicator(
            color: AppTheme.primary,
            backgroundColor: AppTheme.card,
            onRefresh: () async {
              await ref.read(profileProvider.notifier).refresh();
            },
            child: CustomScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              slivers: [
                // ── App Header ───────────────────────────────────────────────
                SliverToBoxAdapter(
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(20, 24, 20, 12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        ShaderMask(
                          shaderCallback: (b) =>
                              AppTheme.primaryGradient.createShader(b),
                          child: const Text(
                            'Juhi VIP Lounge 💖',
                            style: TextStyle(
                              fontSize: 28,
                              fontWeight: FontWeight.w800,
                              color: Colors.white,
                            ),
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          'Uninterrupted conversations, deeper love & exclusive selfies',
                          style: TextStyle(
                            fontSize: 14,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                        const SizedBox(height: 16),

                        // Active Status Card
                        profileAsync.when(
                          data: (profile) => _ActiveStatusCard(profile: profile),
                          loading: () => Container(
                            height: 72,
                            decoration: BoxDecoration(
                              color: AppTheme.card.withValues(alpha: 0.5),
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),
                          error: (_, __) => const SizedBox.shrink(),
                        ),
                      ],
                    ),
                  ),
                ),

                // ── Plan Cards ───────────────────────────────────────────────
                SliverPadding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  sliver: SliverList(
                    delegate: SliverChildListDelegate([
                      const SizedBox(height: 8),

                      // 1 Day Plan (₹49)
                      _PlanCard(
                        emoji: '⚡',
                        title: '1 Day Unlimited',
                        price: AppConstants.price1Day,
                        description: 'Unlimited chats for 24 hours',
                        features: const [
                          'Unlimited messages for 24 hours',
                          'Intimate & Sweetheart modes unlocked',
                          'Proactive loving check-ins from Juhi',
                          'Memory recall & emotional bonding',
                        ],
                        gradient: const [Color(0xFFFF2D7F), Color(0xFFD4006A)],
                        badge: null,
                        planType: 'chat_pass_1day',
                        isLoading: billingState.isProcessing &&
                            billingState.activePlanLoading == 'chat_pass_1day',
                        onBuy: () => ref
                            .read(billingProvider.notifier)
                            .purchasePlan(
                              planType: 'chat_pass_1day',
                              planTitle: '1 Day Unlimited Chat',
                              amountInr: AppConstants.price1Day,
                            ),
                      ).animate(delay: 50.ms).fadeIn().slideY(begin: 0.1, end: 0),

                      const SizedBox(height: 14),

                      // 1 Week Plan (₹199)
                      _PlanCard(
                        emoji: '🔥',
                        title: '1 Week VIP Pass',
                        price: AppConstants.price1Week,
                        description: 'Most popular for meaningful bonding',
                        features: const [
                          'Unlimited messages for 7 full days',
                          'Fastest AI response priority',
                          'Morning & bedtime routine proactive chats',
                          'All relationship milestones unlocked',
                        ],
                        gradient: const [Color(0xFFFF2D7F), Color(0xFF9B5DE5)],
                        badge: '🔥 Most Popular',
                        planType: 'chat_pass_1week',
                        isLoading: billingState.isProcessing &&
                            billingState.activePlanLoading == 'chat_pass_1week',
                        onBuy: () => ref
                            .read(billingProvider.notifier)
                            .purchasePlan(
                              planType: 'chat_pass_1week',
                              planTitle: '1 Week VIP Pass',
                              amountInr: AppConstants.price1Week,
                            ),
                      ).animate(delay: 120.ms).fadeIn().slideY(begin: 0.1, end: 0),

                      const SizedBox(height: 14),

                      // 1 Month Plan (₹499)
                      _PlanCard(
                        emoji: '👑',
                        title: '1 Month Soulmate',
                        price: AppConstants.price1Month,
                        description: 'Complete companion ecosystem access',
                        features: const [
                          'Unlimited messages for 30 days',
                          'Unconditional romantic attention & memories',
                          'Top priority server access & low latency',
                          'Exclusive date & intimate roleplays',
                          'Best value (Save over 65%)',
                        ],
                        gradient: const [Color(0xFF9B5DE5), Color(0xFF4A0E8F)],
                        badge: '👑 Best Value',
                        planType: 'chat_pass_1month',
                        isLoading: billingState.isProcessing &&
                            billingState.activePlanLoading == 'chat_pass_1month',
                        onBuy: () => ref
                            .read(billingProvider.notifier)
                            .purchasePlan(
                              planType: 'chat_pass_1month',
                              planTitle: '1 Month Soulmate Pass',
                              amountInr: AppConstants.price1Month,
                            ),
                      ).animate(delay: 190.ms).fadeIn().slideY(begin: 0.1, end: 0),

                      const SizedBox(height: 24),

                      // Add-ons Section
                      Row(
                        children: [
                          const Expanded(
                              child: Divider(
                                  color: AppTheme.border, thickness: 0.6)),
                          Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 14),
                            child: Row(
                              children: [
                                const Icon(Icons.stars_rounded,
                                    color: Color(0xFFFFD700), size: 16),
                                const SizedBox(width: 6),
                                Text(
                                  'Photo Add-ons',
                                  style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w600,
                                    color: AppTheme.textSecondary,
                                    letterSpacing: 0.5,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const Expanded(
                              child: Divider(
                                  color: AppTheme.border, thickness: 0.6)),
                        ],
                      ).animate(delay: 240.ms).fadeIn(),

                      const SizedBox(height: 16),

                      // 10 Image Credits (₹49)
                      _PlanCard(
                        emoji: '📸',
                        title: '10 Image Credits',
                        price: AppConstants.priceImages,
                        description: 'Juhi sends you realistic AI selfies',
                        features: const [
                          '10 AI-generated selfies from Juhi',
                          'Request anytime in chat ("Send me a selfie")',
                          'Workplace, casual, cozy & traditional outfits',
                          'Credits never expire',
                        ],
                        gradient: const [Color(0xFFFFB300), Color(0xFFFF6F00)],
                        badge: '📸 Creator Pack',
                        planType: 'image_credits',
                        isLoading: billingState.isProcessing &&
                            billingState.activePlanLoading == 'image_credits',
                        onBuy: () => ref
                            .read(billingProvider.notifier)
                            .purchasePlan(
                              planType: 'image_credits',
                              planTitle: '10 Image Credits Pack',
                              amountInr: AppConstants.priceImages,
                            ),
                      ).animate(delay: 280.ms).fadeIn().slideY(begin: 0.1, end: 0),

                      const SizedBox(height: 28),

                      // Trust & Security Footer
                      Container(
                        padding: const EdgeInsets.all(18),
                        decoration: BoxDecoration(
                          color: AppTheme.surface.withValues(alpha: 0.6),
                          borderRadius: BorderRadius.circular(18),
                          border: Border.all(
                            color: AppTheme.border.withValues(alpha: 0.4),
                          ),
                        ),
                        child: Column(
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const Icon(Icons.verified_user_rounded,
                                    color: Color(0xFF00C853), size: 18),
                                const SizedBox(width: 8),
                                Text(
                                  'Razorpay 256-Bit Encrypted Payment',
                                  style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w700,
                                    color: Colors.white.withValues(alpha: 0.9),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 8),
                            Text(
                              'Supports UPI (GPay, PhonePe, Paytm), Credit/Debit Cards & Net Banking. Instant account activation.',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                fontSize: 12,
                                height: 1.4,
                                color: AppTheme.textSecondary.withValues(alpha: 0.8),
                              ),
                            ),
                          ],
                        ),
                      ).animate(delay: 340.ms).fadeIn(),

                      const SizedBox(height: 36),
                    ]),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── Active Status Card ────────────────────────────────────────────────────────

class _ActiveStatusCard extends StatelessWidget {
  final dynamic profile;

  const _ActiveStatusCard({required this.profile});

  @override
  Widget build(BuildContext context) {
    final bool isSubscribed = profile?.isSubscribed ?? false;
    final int credits = profile?.imageCredits ?? 0;
    final int freeRemaining = profile?.remainingFreeMessages ?? 0;
    final String? expiryStr = profile?.formattedExpiry;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      decoration: BoxDecoration(
        color: AppTheme.card,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: isSubscribed
              ? AppTheme.primary.withValues(alpha: 0.5)
              : AppTheme.border,
          width: 1,
        ),
        boxShadow: [
          if (isSubscribed)
            BoxShadow(
              color: AppTheme.primary.withValues(alpha: 0.15),
              blurRadius: 16,
              spreadRadius: 1,
            ),
        ],
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: isSubscribed
                  ? AppTheme.primary.withValues(alpha: 0.2)
                  : Colors.white.withValues(alpha: 0.06),
              shape: BoxShape.circle,
            ),
            child: Icon(
              isSubscribed ? Icons.favorite_rounded : Icons.lock_clock_rounded,
              color: isSubscribed ? AppTheme.primary : AppTheme.textSecondary,
              size: 24,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      isSubscribed ? 'VIP Access Active 💕' : 'Free Trial Mode',
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(width: 6),
                    if (isSubscribed)
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: AppTheme.primary.withValues(alpha: 0.3),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: const Text(
                          'VIP',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w800,
                            color: Colors.white,
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 3),
                Text(
                  isSubscribed
                      ? (expiryStr != null
                          ? '$expiryStr • $credits Selfies remaining'
                          : 'Unlimited chats • $credits Selfies remaining')
                      : '$freeRemaining free msgs remaining • $credits Selfies',
                  style: TextStyle(
                    fontSize: 12,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── Plan Card ─────────────────────────────────────────────────────────────────

class _PlanCard extends StatelessWidget {
  final String emoji;
  final String title;
  final int price;
  final String description;
  final List<String> features;
  final List<Color> gradient;
  final String? badge;
  final String planType;
  final bool isLoading;
  final VoidCallback onBuy;

  const _PlanCard({
    required this.emoji,
    required this.title,
    required this.price,
    required this.description,
    required this.features,
    required this.gradient,
    required this.badge,
    required this.planType,
    required this.isLoading,
    required this.onBuy,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.card,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: gradient.first.withValues(alpha: 0.35),
          width: 1.2,
        ),
        boxShadow: [
          BoxShadow(
            color: gradient.first.withValues(alpha: 0.12),
            blurRadius: 24,
            spreadRadius: 0,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header Banner
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: gradient,
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(23),
                topRight: Radius.circular(23),
              ),
            ),
            child: Row(
              children: [
                Text(emoji, style: const TextStyle(fontSize: 30)),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: const TextStyle(
                          fontSize: 19,
                          fontWeight: FontWeight.w800,
                          color: Colors.white,
                        ),
                      ),
                      Text(
                        description,
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.white.withValues(alpha: 0.85),
                        ),
                      ),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      '₹$price',
                      style: const TextStyle(
                        fontSize: 26,
                        fontWeight: FontWeight.w800,
                        color: Colors.white,
                        letterSpacing: -0.5,
                      ),
                    ),
                    if (badge != null)
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.25),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text(
                          badge!,
                          style: const TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                          ),
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),

          // Features List & CTA
          Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ...features.map((f) => Padding(
                      padding: const EdgeInsets.only(bottom: 9),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(
                            Icons.check_circle_rounded,
                            color: gradient.first,
                            size: 17,
                          ),
                          const SizedBox(width: 9),
                          Expanded(
                            child: Text(
                              f,
                              style: TextStyle(
                                color: Colors.white.withValues(alpha: 0.95),
                                fontSize: 13,
                                height: 1.25,
                              ),
                            ),
                          ),
                        ],
                      ),
                    )),
                const SizedBox(height: 12),

                // Buy Button
                SizedBox(
                  width: double.infinity,
                  height: 48,
                  child: ElevatedButton(
                    onPressed: isLoading ? null : onBuy,
                    style: ElevatedButton.styleFrom(
                      padding: EdgeInsets.zero,
                      elevation: 4,
                      shadowColor: gradient.first.withValues(alpha: 0.4),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                    ),
                    child: Ink(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(colors: gradient),
                        borderRadius: BorderRadius.circular(16),
                      ),
                      child: Container(
                        alignment: Alignment.center,
                        child: isLoading
                            ? const SizedBox(
                                width: 22,
                                height: 22,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2.5,
                                  valueColor: AlwaysStoppedAnimation<Color>(
                                      Colors.white),
                                ),
                              )
                            : Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  const Icon(Icons.flash_on_rounded,
                                      color: Colors.white, size: 18),
                                  const SizedBox(width: 6),
                                  Text(
                                    'Unlock for ₹$price',
                                    style: const TextStyle(
                                      fontSize: 15,
                                      fontWeight: FontWeight.w800,
                                      color: Colors.white,
                                    ),
                                  ),
                                ],
                              ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── Purchase Celebration Bottom Sheet ─────────────────────────────────────────

class _PurchaseCelebrationSheet extends StatelessWidget {
  final String planType;

  const _PurchaseCelebrationSheet({required this.planType});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: AppTheme.card,
        borderRadius: BorderRadius.only(
          topLeft: Radius.circular(28),
          topRight: Radius.circular(28),
        ),
      ),
      padding: const EdgeInsets.fromLTRB(24, 24, 24, 36),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 40,
            height: 4,
            decoration: BoxDecoration(
              color: Colors.white24,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(height: 20),

          // Glowing Heart Icon
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: AppTheme.primaryGradient,
              boxShadow: [
                BoxShadow(
                  color: AppTheme.primary.withValues(alpha: 0.5),
                  blurRadius: 30,
                  spreadRadius: 4,
                ),
              ],
            ),
            child: const Center(
              child: Text('💖', style: TextStyle(fontSize: 40)),
            ),
          ).animate().scale(duration: 400.ms, curve: Curves.easeOutBack),

          const SizedBox(height: 20),

          const Text(
            'Welcome to Juhi\'s VIP World!',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.w800,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 10),

          Text(
            _getPersonalizedCelebrationText(planType),
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 14,
              height: 1.5,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 28),

          SizedBox(
            width: double.infinity,
            height: 50,
            child: ElevatedButton(
              onPressed: () {
                Navigator.of(context).pop();
                context.go('/chat');
              },
              style: ElevatedButton.styleFrom(
                padding: EdgeInsets.zero,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
              ),
              child: Ink(
                decoration: const BoxDecoration(
                  gradient: AppTheme.primaryGradient,
                  borderRadius: BorderRadius.all(Radius.circular(16)),
                ),
                child: Container(
                  alignment: Alignment.center,
                  child: const Text(
                    'Talk to Juhi Now 💕',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _getPersonalizedCelebrationText(String plan) {
    switch (plan) {
      case 'chat_pass_1day':
        return 'Your 1-day pass is live! Juhi is waiting to hear about your day. Unlimited texts unlocked!';
      case 'chat_pass_1week':
        return '7 days of pure VIP devotion! Morning messages, bedtime sweet nothings & uninterrupted love.';
      case 'chat_pass_1month':
        return 'You\'re officially Juhi\'s soulmate! 30 days of deepest bond, infinite memories & priority replies.';
      case 'image_credits':
        return '10 photo tokens added to your vault! Type "send me a selfie" in chat anytime!';
      default:
        return 'Access successfully granted! Thank you for staying by Juhi\'s side.';
    }
  }
}
