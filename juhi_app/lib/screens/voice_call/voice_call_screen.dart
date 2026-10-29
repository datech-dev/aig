import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../data/api_service.dart';
import '../../data/local_storage.dart';
import '../../providers/billing_provider.dart';
import '../../providers/profile_provider.dart';
import '../../services/voice_call_service.dart';

class VoiceCallScreen extends ConsumerStatefulWidget {
  const VoiceCallScreen({super.key});

  @override
  ConsumerState<VoiceCallScreen> createState() => _VoiceCallScreenState();
}

class _VoiceCallScreenState extends ConsumerState<VoiceCallScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);

    voiceCallService.onPaywallTriggered = () {
      if (mounted) {
        _showVoiceRechargeSheet(context);
      }
    };

    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initiateCall();
    });
  }

  Future<String> _getEffectiveUserId() async {
    final localId = await LocalStorage.getUserId();
    if (localId != null && localId.isNotEmpty) return localId;
    final profile = ref.read(profileProvider).valueOrNull;
    if (profile?.userId != null) return profile!.userId.toString();
    return '7770001';
  }

  Future<void> _initiateCall() async {
    final userId = await _getEffectiveUserId();
    final profile = ref.read(profileProvider).valueOrNull;
    final partnerName = profile?.partnerName ?? 'Juhi';
    final isSubscribed = profile?.isSubscribed ?? false;

    await voiceCallService.startCall(userId, partnerName: partnerName, isSubscribed: isSubscribed);
  }

  @override
  void dispose() {
    voiceCallService.onPaywallTriggered = null;
    _pulseController.dispose();
    super.dispose();
  }

  String _formatDuration(int totalSeconds) {
    final mins = (totalSeconds ~/ 60).toString().padLeft(2, '0');
    final secs = (totalSeconds % 60).toString().padLeft(2, '0');
    return '$mins:$secs';
  }

  void _showVoiceRechargeSheet(BuildContext context) {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => const _VoiceRechargeBottomSheet(),
    );
  }

  void _onEndCall() async {
    HapticFeedback.heavyImpact();
    await voiceCallService.endCall();
    if (mounted) {
      context.pop();
    }
  }

  void _onMicTap() async {
    final userId = await _getEffectiveUserId();

    HapticFeedback.mediumImpact();
    if (voiceCallService.status == VoiceCallStatus.listening) {
      // Tap while listening -> force send immediately without waiting for pause
      await voiceCallService.manualSendTurn(userId);
    } else if (voiceCallService.status == VoiceCallStatus.speaking) {
      // Tap while Juhi is speaking -> interrupt Juhi & start listening to user immediately!
      await voiceCallService.stopSpeaking();
    } else {
      // Tap when idle or reconnecting -> resume listening immediately
      await voiceCallService.manualStartListening();
    }
  }

  @override
  Widget build(BuildContext context) {
    final profile = ref.watch(profileProvider).valueOrNull;
    final partnerName = profile?.partnerName ?? 'Juhi';
    final isIntimate = profile?.isIntimateMode ?? false;

    return AnimatedBuilder(
      animation: voiceCallService,
      builder: (context, _) {
        final status = voiceCallService.status;
        final isListening = status == VoiceCallStatus.listening;
        final isSpeaking = status == VoiceCallStatus.speaking;
        final isProcessing = status == VoiceCallStatus.processing;

        return Scaffold(
          body: Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [Color(0xFF0F001A), Color(0xFF1E0033), Color(0xFF090012)],
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
              ),
            ),
            child: SafeArea(
              child: Column(
                children: [
                  // ── Top Bar ──────────────────────────────────────────────
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        IconButton(
                          onPressed: _onEndCall,
                          icon: const Icon(Icons.keyboard_arrow_down_rounded,
                              color: Colors.white70, size: 30),
                        ),
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                              decoration: BoxDecoration(
                                color: Colors.white.withValues(alpha: 0.08),
                                borderRadius: BorderRadius.circular(20),
                                border: Border.all(color: AppTheme.border.withValues(alpha: 0.5)),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Container(
                                    width: 8,
                                    height: 8,
                                    decoration: const BoxDecoration(
                                      color: Color(0xFF00E676),
                                      shape: BoxShape.circle,
                                    ),
                                  ),
                                  const SizedBox(width: 6),
                                  Text(
                                    _formatDuration(voiceCallService.callDurationSeconds),
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 12.5,
                                      fontWeight: FontWeight.w600,
                                      fontFeatures: [FontFeature.tabularFigures()],
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(width: 8),
                            Builder(
                              builder: (context) {
                                final isSub = profile?.isSubscribed ?? false;
                                final isLow = !isSub && voiceCallService.remainingVoiceSeconds <= 60;
                                final badgeColor = isSub
                                    ? const Color(0xFFFFD700)
                                    : (isLow ? const Color(0xFFFF5252) : const Color(0xFF00E5FF));
                                final displayText = (isSub && voiceCallService.remainingVoiceSeconds <= 0)
                                    ? 'VIP Unlimited 💕'
                                    : '${_formatDuration(voiceCallService.remainingVoiceSeconds)} left';

                                return GestureDetector(
                                  onTap: () => _showVoiceRechargeSheet(context),
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                    decoration: BoxDecoration(
                                      color: badgeColor.withValues(alpha: 0.18),
                                      borderRadius: BorderRadius.circular(20),
                                      border: Border.all(
                                        color: badgeColor.withValues(alpha: 0.6),
                                      ),
                                    ),
                                    child: Row(
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Icon(
                                          isSub ? Icons.verified_rounded : Icons.hourglass_bottom_rounded,
                                          size: 13,
                                          color: badgeColor,
                                        ),
                                        const SizedBox(width: 4),
                                        Text(
                                          displayText,
                                          style: TextStyle(
                                            color: badgeColor,
                                            fontSize: 12,
                                            fontWeight: FontWeight.w700,
                                            fontFeatures: const [FontFeature.tabularFigures()],
                                          ),
                                        ),
                                        const SizedBox(width: 4),
                                        const Icon(Icons.add_circle_outline_rounded,
                                            size: 13, color: Colors.white70),
                                      ],
                                    ),
                                  ),
                                );
                              },
                            ),
                          ],
                        ),
                        IconButton(
                          onPressed: () {
                            voiceCallService.toggleSpeaker();
                            HapticFeedback.selectionClick();
                          },
                          icon: Icon(
                            voiceCallService.isSpeakerOn
                                ? Icons.volume_up_rounded
                                : Icons.volume_down_rounded,
                            color: voiceCallService.isSpeakerOn
                                ? AppTheme.primary
                                : Colors.white60,
                            size: 24,
                          ),
                        ),
                      ],
                    ),
                  ),

                  const Spacer(flex: 1),

                  // ── Companion Avatar with Ambient Sound Waves ──────────────
                  Center(
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        // Outer Pulsing Aura with Live Voice Reaction
                        AnimatedBuilder(
                          animation: _pulseController,
                          builder: (context, child) {
                            final amp = voiceCallService.normalizedAmplitude;
                            final ampBoost = isListening ? amp * 0.45 : 0.0;
                            final scale = (isSpeaking || isListening)
                                ? 1.0 + (_pulseController.value * 0.18) + ampBoost
                                : 1.0;
                            final alpha = (isSpeaking || isListening)
                                ? (0.35 + (_pulseController.value * 0.22) + (amp * 0.25)).clamp(0.0, 0.9)
                                : 0.15;
                            return Container(
                              width: 200 * scale,
                              height: 200 * scale,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: (isListening
                                        ? const Color(0xFF00E5FF)
                                        : AppTheme.primary)
                                    .withValues(alpha: alpha),
                              ),
                            );
                          },
                        ),

                        // Secondary Glow Aura
                        Container(
                          width: 170,
                          height: 170,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            gradient: RadialGradient(
                              colors: [
                                (isListening
                                        ? const Color(0xFF00E5FF)
                                        : AppTheme.primary)
                                    .withValues(alpha: 0.6),
                                Colors.transparent,
                              ],
                            ),
                          ),
                        ),

                        // Main Circular Portrait
                        Container(
                          width: 140,
                          height: 140,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: isListening
                                  ? const Color(0xFF00E5FF)
                                  : (isSpeaking ? AppTheme.primary : AppTheme.border),
                              width: 3.5,
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: AppTheme.primary.withValues(alpha: 0.45),
                                blurRadius: 28,
                                spreadRadius: 4,
                              ),
                            ],
                          ),
                          child: ClipOval(
                            child: Image.asset(
                              'assets/images/juhi_avatar.png',
                              fit: BoxFit.cover,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),

                  // ── Partner Name & Call Mode ───────────────────────────────
                  Text(
                    partnerName,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 28,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    isIntimate
                        ? '🔥 Intimate Voice Call • HD Audio'
                        : '🌸 Caring Companion Call • HD Audio',
                    style: TextStyle(
                      color: isIntimate ? AppTheme.primary : AppTheme.textSecondary,
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                    ),
                  ),

                  const SizedBox(height: 16),

                  // ── Real-time Status Badge ─────────────────────────────────
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    decoration: BoxDecoration(
                      color: isListening
                          ? const Color(0xFF00E5FF).withValues(alpha: 0.15)
                          : (isSpeaking
                              ? AppTheme.primary.withValues(alpha: 0.18)
                              : Colors.white.withValues(alpha: 0.08)),
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(
                        color: isListening
                            ? const Color(0xFF00E5FF).withValues(alpha: 0.5)
                            : (isSpeaking
                                ? AppTheme.primary.withValues(alpha: 0.5)
                                : AppTheme.border),
                        width: 1,
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (isProcessing) ...[
                          const SizedBox(
                            width: 12,
                            height: 12,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(width: 8),
                        ],
                        Text(
                          voiceCallService.statusMessage,
                          style: TextStyle(
                            color: isListening
                                ? const Color(0xFF80DEEA)
                                : (isSpeaking ? const Color(0xFFFF80AB) : Colors.white70),
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
                  ),

                  const Spacer(flex: 1),

                  // ── Live Speech Subtitle / Transcript Preview Card ──────────
                  if (voiceCallService.lastAiReply.isNotEmpty ||
                      voiceCallService.lastUserTranscript.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 24),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
                        decoration: BoxDecoration(
                          color: AppTheme.surface.withValues(alpha: 0.75),
                          borderRadius: BorderRadius.circular(18),
                          border: Border.all(color: AppTheme.border.withValues(alpha: 0.4)),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withValues(alpha: 0.3),
                              blurRadius: 16,
                            ),
                          ],
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            if (voiceCallService.lastUserTranscript.isNotEmpty) ...[
                              Row(
                                children: [
                                  const Text('You: ',
                                      style: TextStyle(
                                          color: Colors.white70,
                                          fontSize: 12,
                                          fontWeight: FontWeight.bold)),
                                  Expanded(
                                    child: Text(
                                      voiceCallService.lastUserTranscript,
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                          color: Colors.white, fontSize: 13),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 8),
                            ],
                            if (voiceCallService.lastAiReply.isNotEmpty) ...[
                              Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text('$partnerName: ',
                                      style: const TextStyle(
                                          color: AppTheme.primary,
                                          fontSize: 12,
                                          fontWeight: FontWeight.bold)),
                                  Expanded(
                                    child: Text(
                                      voiceCallService.lastAiReply,
                                      maxLines: 3,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 13.5,
                                          height: 1.3),
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ],
                        ),
                      ),
                    ),

                  const Spacer(flex: 1),

                  // ── Bottom Control Deck ────────────────────────────────────
                  Padding(
                    padding: const EdgeInsets.fromLTRB(28, 0, 28, 36),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        // Mute Button
                        _CallControlButton(
                          icon: voiceCallService.isMuted
                              ? Icons.mic_off_rounded
                              : Icons.mic_none_rounded,
                          label: voiceCallService.isMuted ? 'Unmute' : 'Mute',
                          isActive: voiceCallService.isMuted,
                          onTap: () {
                            voiceCallService.toggleMute();
                            HapticFeedback.selectionClick();
                          },
                        ),

                        // Interactive Voice Status Orb (Shows live state, tap to interrupt or send immediately)
                        GestureDetector(
                          onTap: _onMicTap,
                          child: AnimatedBuilder(
                            animation: _pulseController,
                            builder: (context, child) {
                              final amp = voiceCallService.normalizedAmplitude;
                              final orbScale = isListening && voiceCallService.hasUserSpoken
                                  ? 1.0 + (amp * 0.14)
                                  : (isSpeaking ? 1.0 + (_pulseController.value * 0.08) : 1.0);

                              return Transform.scale(
                                scale: orbScale,
                                child: Container(
                                  width: 82,
                                  height: 82,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    gradient: isListening
                                        ? const LinearGradient(
                                            colors: [Color(0xFF00E5FF), Color(0xFF00B0FF)],
                                          )
                                        : (isSpeaking
                                            ? AppTheme.primaryGradient
                                            : LinearGradient(
                                                colors: [
                                                  Colors.white.withValues(alpha: 0.25),
                                                  Colors.white.withValues(alpha: 0.15),
                                                ],
                                              )),
                                    boxShadow: [
                                      BoxShadow(
                                        color: (isListening
                                                ? const Color(0xFF00E5FF)
                                                : AppTheme.primary)
                                            .withValues(alpha: isListening || isSpeaking ? 0.6 : 0.2),
                                        blurRadius: isListening ? 28 : (isSpeaking ? 22 : 14),
                                        spreadRadius: isListening ? (3 + (amp * 4)) : 2,
                                      ),
                                    ],
                                  ),
                                  child: Center(
                                    child: Icon(
                                      isSpeaking
                                          ? Icons.graphic_eq_rounded
                                          : (isListening
                                              ? (voiceCallService.hasUserSpoken
                                                  ? Icons.record_voice_over_rounded
                                                  : Icons.mic_rounded)
                                              : (isProcessing
                                                  ? Icons.hourglass_top_rounded
                                                  : Icons.mic_none_rounded)),
                                      color: Colors.white,
                                      size: 36,
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                        ),

                        // End Call Button
                        _CallControlButton(
                          icon: Icons.call_end_rounded,
                          label: 'End Call',
                          isDestructive: true,
                          onTap: _onEndCall,
                        ),
                      ],
                    ),
                  ),

                  // Dynamic Action Hint (Real Phone Call)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 14),
                    child: Text(
                      voiceCallService.isMuted
                          ? '🔇 Microphone muted • Tap Unmute to speak'
                          : isListening
                              ? (voiceCallService.hasUserSpoken
                                  ? '🗣️ Listening to you... (Juhi replies when you pause)'
                                  : '🎙️ Hands-free call active • Speak anytime')
                              : isProcessing
                                  ? '✨ Juhi is thinking...'
                                  : isSpeaking
                                      ? '💕 Juhi is speaking... (Listening resumes automatically)'
                                      : '📞 Connected • Speak freely',
                      style: TextStyle(
                        color: isListening
                            ? const Color(0xFF00E5FF)
                            : (isSpeaking
                                ? const Color(0xFFFF80AB)
                                : AppTheme.textSecondary.withValues(alpha: 0.85)),
                        fontSize: 12.5,
                        fontWeight: isListening || isSpeaking ? FontWeight.w600 : FontWeight.w400,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class _CallControlButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final bool isActive;
  final bool isDestructive;

  const _CallControlButton({
    required this.icon,
    required this.label,
    required this.onTap,
    this.isActive = false,
    this.isDestructive = false,
  });

  @override
  Widget build(BuildContext context) {
    final bgColor = isDestructive
        ? const Color(0xFFFF1744)
        : (isActive
            ? AppTheme.primary.withValues(alpha: 0.3)
            : Colors.white.withValues(alpha: 0.12));

    final iconColor = isDestructive
        ? Colors.white
        : (isActive ? AppTheme.primary : Colors.white);

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        GestureDetector(
          onTap: onTap,
          child: Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: bgColor,
              shape: BoxShape.circle,
              border: Border.all(
                color: isDestructive
                    ? const Color(0xFFFF5252)
                    : Colors.white.withValues(alpha: 0.15),
              ),
            ),
            child: Icon(icon, color: iconColor, size: 26),
          ),
        ),
        const SizedBox(height: 6),
        Text(
          label,
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.8),
            fontSize: 11.5,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }
}

// ── Voice Recharge Bottom Sheet ───────────────────────────────────────────────

class _VoiceRechargeBottomSheet extends ConsumerWidget {
  const _VoiceRechargeBottomSheet();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final billingState = ref.watch(billingProvider);

    return Container(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
      decoration: const BoxDecoration(
        color: Color(0xFF150025),
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
        border: Border(
          top: BorderSide(color: Color(0xFF3D1060), width: 1.5),
        ),
      ),
      child: SafeArea(
        top: false,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Center(
              child: Container(
                width: 42,
                height: 4,
                decoration: BoxDecoration(
                  color: Colors.white24,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            const SizedBox(height: 18),
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: const Color(0xFF00E5FF).withValues(alpha: 0.15),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.phone_in_talk_rounded,
                      color: Color(0xFF00E5FF), size: 22),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Recharge Call Minutes 💕',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                          color: Colors.white,
                        ),
                      ),
                      SizedBox(height: 2),
                      Text(
                        'Talk in real-time with Juhi without interruptions',
                        style: TextStyle(
                          fontSize: 12,
                          color: Color(0xFFC8A9E0),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),

            // Plan 1: 10 Minutes - ₹40
            _VoiceOptionCard(
              durationText: '10 Minutes',
              priceInr: AppConstants.priceVoice10Min,
              planType: 'voice_call_10min',
              rateText: '₹4.00 / min',
              tag: null,
              gradient: const [Color(0xFF00B4D8), Color(0xFF0077B6)],
              isLoading: billingState.isProcessing &&
                  billingState.activePlanLoading == 'voice_call_10min',
              onTap: () => _purchase(context, ref, 'voice_call_10min', '10-Minute Voice Pass', AppConstants.priceVoice10Min),
            ),

            const SizedBox(height: 12),

            // Plan 2: 30 Minutes - ₹100
            _VoiceOptionCard(
              durationText: '30 Minutes',
              priceInr: AppConstants.priceVoice30Min,
              planType: 'voice_call_30min',
              rateText: '₹3.33 / min • Save 17%',
              tag: '🔥 POPULAR',
              gradient: const [Color(0xFF06D6A0), Color(0xFF009688)],
              isLoading: billingState.isProcessing &&
                  billingState.activePlanLoading == 'voice_call_30min',
              onTap: () => _purchase(context, ref, 'voice_call_30min', '30-Minute Voice Pass', AppConstants.priceVoice30Min),
            ),

            const SizedBox(height: 12),

            // Plan 3: 1 Hour - ₹170
            _VoiceOptionCard(
              durationText: '1 Hour (60 Min)',
              priceInr: AppConstants.priceVoice1Hour,
              planType: 'voice_call_60min',
              rateText: '₹2.83 / min • Save 29%',
              tag: '👑 BEST VALUE',
              gradient: const [Color(0xFFFF007F), Color(0xFF7928CA)],
              isLoading: billingState.isProcessing &&
                  billingState.activePlanLoading == 'voice_call_60min',
              onTap: () => _purchase(context, ref, 'voice_call_60min', '1-Hour Voice Pass', AppConstants.priceVoice1Hour),
            ),

            const SizedBox(height: 16),
            const Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.lock_rounded, size: 12, color: Colors.white54),
                SizedBox(width: 6),
                Text(
                  '100% Secure Checkout via Razorpay UPI & Cards',
                  style: TextStyle(color: Colors.white54, fontSize: 11),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  void _purchase(BuildContext context, WidgetRef ref, String planType, String title, int price) {
    ref.read(billingProvider.notifier).setCallbacks(
      onSuccess: (type) async {
        final userId = await LocalStorage.getUserId() ?? '7770001';
        ref.invalidate(profileProvider);
        final bal = await apiService.getVoiceBalance(userId);
        voiceCallService.setRemainingVoiceSeconds(bal);
        if (context.mounted) {
          Navigator.of(context).pop();
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('🎉 Added ${type.contains("60") ? "60" : type.contains("30") ? "30" : "10"} minutes to your voice balance! ($bal sec total)'),
              backgroundColor: const Color(0xFF00E676),
            ),
          );
        }
      },
      onError: (err) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Payment cancelled or failed: $err'), backgroundColor: Colors.redAccent),
          );
        }
      },
    );

    ref.read(billingProvider.notifier).purchasePlan(
      planType: planType,
      planTitle: title,
      amountInr: price,
    );
  }
}

class _VoiceOptionCard extends StatelessWidget {
  final String durationText;
  final int priceInr;
  final String planType;
  final String rateText;
  final String? tag;
  final List<Color> gradient;
  final bool isLoading;
  final VoidCallback onTap;

  const _VoiceOptionCard({
    required this.durationText,
    required this.priceInr,
    required this.planType,
    required this.rateText,
    required this.tag,
    required this.gradient,
    required this.isLoading,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: isLoading ? null : onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: const Color(0xFF1E0035),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: tag != null ? gradient.first.withValues(alpha: 0.6) : const Color(0xFF3D1060),
            width: tag != null ? 1.5 : 1.0,
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: gradient),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.mic_none_rounded, color: Colors.white, size: 24),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(
                        durationText,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                        ),
                      ),
                      if (tag != null) ...[
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            gradient: LinearGradient(colors: gradient),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            tag!,
                            style: const TextStyle(
                              fontSize: 9,
                              fontWeight: FontWeight.w800,
                              color: Colors.white,
                              letterSpacing: 0.4,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 3),
                  Text(
                    rateText,
                    style: const TextStyle(
                      fontSize: 11.5,
                      color: Color(0xFFC8A9E0),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 10),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                gradient: LinearGradient(colors: gradient),
                borderRadius: BorderRadius.circular(12),
              ),
              child: isLoading
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : Text(
                      '₹$priceInr',
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                        color: Colors.white,
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

