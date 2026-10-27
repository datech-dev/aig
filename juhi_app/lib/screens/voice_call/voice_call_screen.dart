import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme.dart';
import '../../data/local_storage.dart';
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
  bool _isHoldingMic = false;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);

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

    await voiceCallService.startCall(userId, partnerName: partnerName);
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  String _formatDuration(int totalSeconds) {
    final mins = (totalSeconds ~/ 60).toString().padLeft(2, '0');
    final secs = (totalSeconds % 60).toString().padLeft(2, '0');
    return '$mins:$secs';
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
      // Tap while listening -> stop and send!
      setState(() => _isHoldingMic = false);
      await voiceCallService.stopRecordingAndSend(userId);
    } else {
      // Tap to start speaking!
      if (voiceCallService.status == VoiceCallStatus.speaking) {
        await voiceCallService.stopSpeaking();
      }
      setState(() => _isHoldingMic = true);
      await voiceCallService.startRecording();
    }
  }

  void _onMicLongPressStart() async {
    if (voiceCallService.status == VoiceCallStatus.speaking) {
      await voiceCallService.stopSpeaking();
    }
    if (voiceCallService.status != VoiceCallStatus.listening) {
      HapticFeedback.heavyImpact();
      setState(() => _isHoldingMic = true);
      await voiceCallService.startRecording();
    }
  }

  void _onMicLongPressEnd() async {
    final userId = await _getEffectiveUserId();

    setState(() => _isHoldingMic = false);
    HapticFeedback.lightImpact();
    await voiceCallService.stopRecordingAndSend(userId);
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
        final isListening = status == VoiceCallStatus.listening || _isHoldingMic;
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
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
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
                              const SizedBox(width: 8),
                              Text(
                                _formatDuration(voiceCallService.callDurationSeconds),
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 13,
                                  fontWeight: FontWeight.w600,
                                  fontFeatures: [FontFeature.tabularFigures()],
                                ),
                              ),
                            ],
                          ),
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
                        // Outer Pulsing Aura
                        AnimatedBuilder(
                          animation: _pulseController,
                          builder: (context, child) {
                            final scale = (isSpeaking || isListening)
                                ? 1.0 + (_pulseController.value * 0.22)
                                : 1.0;
                            final alpha = (isSpeaking || isListening)
                                ? 0.35 + (_pulseController.value * 0.25)
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

                        // Big Push-To-Talk / Voice Orb (Supports Tap to Talk & Hold to Talk)
                        GestureDetector(
                          onTap: _onMicTap,
                          onLongPressStart: (_) => _onMicLongPressStart(),
                          onLongPressEnd: (_) => _onMicLongPressEnd(),
                          child: AnimatedContainer(
                            duration: const Duration(milliseconds: 200),
                            width: 82,
                            height: 82,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              gradient: isListening
                                  ? const LinearGradient(
                                      colors: [Color(0xFF00E5FF), Color(0xFF00B0FF)],
                                    )
                                  : AppTheme.primaryGradient,
                              boxShadow: [
                                BoxShadow(
                                  color: (isListening
                                          ? const Color(0xFF00E5FF)
                                          : AppTheme.primary)
                                      .withValues(alpha: 0.55),
                                  blurRadius: isListening ? 28 : 16,
                                  spreadRadius: isListening ? 6 : 2,
                                ),
                              ],
                            ),
                            child: Center(
                              child: Icon(
                                isListening
                                    ? Icons.stop_rounded
                                    : Icons.mic_rounded,
                                color: Colors.white,
                                size: 38,
                              ),
                            ),
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

                  // Dynamic Action Hint
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Text(
                      isListening
                          ? '🎙️ Juhi is listening! Tap to send (or release)'
                          : isProcessing
                              ? '✨ Juhi is thinking...'
                              : isSpeaking
                                  ? '💕 Juhi is speaking... (Tap mic to speak)'
                                  : 'Tap to speak (or hold while talking)',
                      style: TextStyle(
                        color: isListening
                            ? const Color(0xFF00E5FF)
                            : AppTheme.textSecondary.withValues(alpha: 0.75),
                        fontSize: 12,
                        fontWeight: isListening ? FontWeight.w600 : FontWeight.w400,
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
