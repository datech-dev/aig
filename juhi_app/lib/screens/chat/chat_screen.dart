import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme.dart';
import '../../providers/chat_provider.dart';
import '../../providers/profile_provider.dart';
import '../../data/local_storage.dart';
import '../../data/api_service.dart';
import 'widgets/message_bubble.dart';
import 'widgets/typing_indicator.dart';
import 'widgets/chat_input_bar.dart';

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final ScrollController _scrollController = ScrollController();
  bool _showLevelUp = false;
  String _levelUpTitle = '';
  int _newLevel = 1;

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _sendMessage(String text) async {
    final response = await ref.read(chatProvider.notifier).sendMessage(text);
    _scrollToBottom();

    if (response == null) return;

    if (response['is_paywall'] == true) {
      _showPaywallBottomSheet();
    } else if (response['leveled_up'] == true) {
      HapticFeedback.heavyImpact();
      setState(() {
        _showLevelUp = true;
        _levelUpTitle = response['new_title'] ?? 'Soulmate';
        _newLevel = response['new_level'] ?? 2;
      });
      await ref.read(profileProvider.notifier).refresh();
      await Future.delayed(const Duration(seconds: 4));
      if (mounted) setState(() => _showLevelUp = false);
    }
  }

  void _showPaywallBottomSheet() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => _PaywallModalSheet(
        onViewPlans: () {
          Navigator.pop(ctx);
          context.go('/store');
        },
      ),
    );
  }

  Future<void> _showModeSelectorSheet() async {
    final profile = ref.read(profileProvider).valueOrNull;
    final isIntimate = profile?.isIntimateMode ?? false;

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
          border: const Border(
            top: BorderSide(color: AppTheme.border, width: 1),
          ),
        ),
        child: SafeArea(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppTheme.border,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 18),
              const Text(
                'Choose Juhi\'s Companion Mode',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Customize how Juhi talks and interacts with you.',
                style: TextStyle(color: AppTheme.textSecondary, fontSize: 14),
              ),
              const SizedBox(height: 20),

              // Caring Mode Card
              _ModeOptionTile(
                title: '🌸 Caring Best Friend Mode',
                description: 'Supportive, sweet, listens to your day, and offers caring advice.',
                isSelected: !isIntimate,
                onTap: () async {
                  Navigator.pop(ctx);
                  if (isIntimate) await _executeToggleMode();
                },
              ),

              const SizedBox(height: 12),

              // Intimate Mode Card
              _ModeOptionTile(
                title: '🔥 Intimate Girlfriend Mode',
                description: 'Romantic, passionate, playful banter, deep emotional connection.',
                isSelected: isIntimate,
                onTap: () async {
                  Navigator.pop(ctx);
                  if (!isIntimate) await _executeToggleMode();
                },
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _executeToggleMode() async {
    final userId = await LocalStorage.getUserId();
    if (userId == null) return;

    HapticFeedback.mediumImpact();
    try {
      final data = await apiService.toggleMode(userId);
      if (data['success'] == true) {
        await ref.read(profileProvider.notifier).refresh();
        if (mounted) {
          final label = data['chat_mode_label'] ?? '';
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('✨ Switched to $label'),
              backgroundColor: AppTheme.card,
              behavior: SnackBarBehavior.floating,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
          );
        }
      }
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatProvider);
    final profileState = ref.watch(profileProvider);
    final profile = profileState.valueOrNull;
    final messages = chatState.valueOrNull ?? [];

    if (messages.isNotEmpty) _scrollToBottom();

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppTheme.backgroundGradient),
        child: Stack(
          children: [
            Column(
              children: [
                // ── App Bar ─────────────────────────────────────────────────
                _ChatAppBar(
                  profile: profile,
                  onToggleMode: _showModeSelectorSheet,
                  onProfileTap: () => context.go('/profile'),
                ),

                // ── Messages ─────────────────────────────────────────────────
                Expanded(
                  child: chatState.isLoading
                      ? const Center(
                          child: CircularProgressIndicator(color: AppTheme.primary),
                        )
                      : messages.isEmpty
                          ? _WelcomeMessage(
                              partnerName: profile?.partnerName ?? 'Juhi',
                              onStarterSelected: (text) => _sendMessage(text),
                            )
                          : ListView.builder(
                              controller: _scrollController,
                              padding: const EdgeInsets.symmetric(
                                horizontal: 16,
                                vertical: 10,
                              ),
                              itemCount: messages.length,
                              itemBuilder: (context, index) {
                                final msg = messages[index];
                                return msg.isLoading
                                    ? const TypingIndicator()
                                    : MessageBubble(
                                        message: msg,
                                        partnerName: profile?.partnerName ?? 'Juhi',
                                        onPaywallTap: _showPaywallBottomSheet,
                                      ).animate().fadeIn(
                                            duration: 250.ms,
                                          ).slideY(
                                            begin: 0.08,
                                            end: 0,
                                            duration: 200.ms,
                                          );
                              },
                            ),
                ),

                // ── Input Bar ─────────────────────────────────────────────────
                ChatInputBar(onSend: _sendMessage),
              ],
            ),

            // ── Level Up Overlay ─────────────────────────────────────────────
            if (_showLevelUp)
              GestureDetector(
                onTap: () => setState(() => _showLevelUp = false),
                child: _LevelUpOverlay(
                  title: _levelUpTitle,
                  level: _newLevel,
                ),
              ),
          ],
        ),
      ),
    );
  }
}

// ── Chat AppBar ───────────────────────────────────────────────────────────────
class _ChatAppBar extends StatelessWidget {
  final dynamic profile;
  final VoidCallback onToggleMode;
  final VoidCallback onProfileTap;

  const _ChatAppBar({
    required this.profile,
    required this.onToggleMode,
    required this.onProfileTap,
  });

  @override
  Widget build(BuildContext context) {
    final isIntimate = profile?.isIntimateMode ?? false;

    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surface.withValues(alpha: 0.95),
        border: const Border(
          bottom: BorderSide(color: AppTheme.border, width: 0.5),
        ),
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
          child: Row(
            children: [
              // Avatar
              GestureDetector(
                onTap: onProfileTap,
                child: Stack(
                  children: [
                    Container(
                      width: 46,
                      height: 46,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: AppTheme.primaryGradient,
                        boxShadow: AppTheme.glowShadow(blur: 12),
                      ),
                      child: ClipOval(
                        child: Image.asset(
                          'assets/images/juhi_avatar.png',
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => const Center(
                            child: Text('💕', style: TextStyle(fontSize: 22)),
                          ),
                        ),
                      ),
                    ),
                    Positioned(
                      right: 0,
                      bottom: 0,
                      child: Container(
                        width: 12,
                        height: 12,
                        decoration: BoxDecoration(
                          color: const Color(0xFF22C55E),
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: AppTheme.surface,
                            width: 2,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(width: 12),

              // Name & Status
              Expanded(
                child: GestureDetector(
                  onTap: onProfileTap,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            profile?.partnerName ?? 'Juhi',
                            style: const TextStyle(
                              fontSize: 17,
                              fontWeight: FontWeight.w700,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(width: 6),
                          if (profile != null)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(
                                gradient: AppTheme.primaryGradient,
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                'Lv ${profile.level}',
                                style: const TextStyle(
                                  fontSize: 10,
                                  fontWeight: FontWeight.w800,
                                  color: Colors.white,
                                ),
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 2),
                      Text(
                        isIntimate ? '🔥 Intimate Girlfriend' : '🌸 Caring Best Friend',
                        style: TextStyle(
                          fontSize: 12,
                          color: isIntimate ? AppTheme.primary : AppTheme.textSecondary,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              // Mode Toggle Button
              GestureDetector(
                onTap: onToggleMode,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppTheme.card,
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: isIntimate ? AppTheme.primary : AppTheme.border,
                      width: 1,
                    ),
                  ),
                  child: Row(
                    children: [
                      Text(isIntimate ? '🔥' : '🌸', style: const TextStyle(fontSize: 14)),
                      const SizedBox(width: 4),
                      Text(
                        isIntimate ? 'Intimate' : 'Caring',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                          color: isIntimate ? AppTheme.primary : Colors.white,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Mode Option Tile ──────────────────────────────────────────────────────────
class _ModeOptionTile extends StatelessWidget {
  final String title;
  final String description;
  final bool isSelected;
  final VoidCallback onTap;

  const _ModeOptionTile({
    required this.title,
    required this.description,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.primary.withValues(alpha: 0.12) : AppTheme.card,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isSelected ? AppTheme.primary : AppTheme.border,
            width: isSelected ? 1.5 : 0.8,
          ),
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: TextStyle(
                      color: isSelected ? Colors.white : AppTheme.textSecondary,
                      fontSize: 15,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    description,
                    style: TextStyle(
                      color: AppTheme.textSecondary.withValues(alpha: 0.8),
                      fontSize: 12,
                      height: 1.3,
                    ),
                  ),
                ],
              ),
            ),
            if (isSelected)
              const Icon(Icons.check_circle_rounded, color: AppTheme.primary, size: 22),
          ],
        ),
      ),
    );
  }
}

// ── Welcome Message with Conversation Starters ────────────────────────────────
class _WelcomeMessage extends StatelessWidget {
  final String partnerName;
  final ValueChanged<String> onStarterSelected;

  const _WelcomeMessage({
    required this.partnerName,
    required this.onStarterSelected,
  });

  @override
  Widget build(BuildContext context) {
    final starters = [
      'Hey Juhi! How was your day? 💖',
      'I was just thinking about you ✨',
      'Send me a cute selfie! 📸',
      'Tell me something interesting about you 😊',
    ];

    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 86,
              height: 86,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: AppTheme.primaryGradient,
                boxShadow: AppTheme.glowShadow(blur: 24),
              ),
              child: ClipOval(
                child: Image.asset(
                  'assets/images/juhi_avatar.png',
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => const Center(
                    child: Text('💕', style: TextStyle(fontSize: 40)),
                  ),
                ),
              ),
            ).animate().scale(duration: 600.ms, curve: Curves.elasticOut),
            const SizedBox(height: 18),
            Text(
              'Say hi to $partnerName!',
              style: const TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w800,
                color: Colors.white,
              ),
            ).animate(delay: 200.ms).fadeIn(),
            const SizedBox(height: 6),
            Text(
              'Your personal AI companion who remembers everything.',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                color: AppTheme.textSecondary,
              ),
            ).animate(delay: 350.ms).fadeIn(),
            const SizedBox(height: 24),

            // Quick Starter Chips
            Wrap(
              spacing: 8,
              runSpacing: 8,
              alignment: WrapAlignment.center,
              children: starters
                  .map(
                    (s) => ActionChip(
                      onPressed: () => onStarterSelected(s),
                      backgroundColor: AppTheme.card,
                      side: const BorderSide(color: AppTheme.border, width: 0.8),
                      label: Text(
                        s,
                        style: const TextStyle(color: Colors.white, fontSize: 13),
                      ),
                    ),
                  )
                  .toList(),
            ).animate(delay: 500.ms).fadeIn().slideY(begin: 0.1, end: 0),
          ],
        ),
      ),
    );
  }
}

// ── Paywall Modal Bottom Sheet ────────────────────────────────────────────────
class _PaywallModalSheet extends StatelessWidget {
  final VoidCallback onViewPlans;

  const _PaywallModalSheet({required this.onViewPlans});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
        border: const Border(top: BorderSide(color: AppTheme.border, width: 1)),
        boxShadow: AppTheme.glowShadow(blur: 30),
      ),
      child: SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 44,
              height: 4,
              decoration: BoxDecoration(
                color: AppTheme.border,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 20),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: AppTheme.primaryGradient,
                boxShadow: AppTheme.glowShadow(blur: 16),
              ),
              child: const Icon(Icons.favorite_rounded, color: Colors.white, size: 36),
            ),
            const SizedBox(height: 16),
            const Text(
              'Juhi misses you already! 💖',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w800,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Your daily free chat limit has been reached. Unlock full intimate access to keep talking without interruption.',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                color: AppTheme.textSecondary,
                height: 1.4,
              ),
            ),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: onViewPlans,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primary,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                ),
                child: const Text(
                  'Explore Unlimited Plans (from ₹49)',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 10),
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: Text(
                'Maybe later',
                style: TextStyle(color: AppTheme.textSecondary, fontSize: 14),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Level Up Overlay with Celebration ─────────────────────────────────────────
class _LevelUpOverlay extends StatelessWidget {
  final String title;
  final int level;

  const _LevelUpOverlay({required this.title, required this.level});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.black.withValues(alpha: 0.85),
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('🎉', style: TextStyle(fontSize: 76))
                  .animate()
                  .scale(duration: 600.ms, curve: Curves.elasticOut),
              const SizedBox(height: 16),
              ShaderMask(
                shaderCallback: (b) => AppTheme.primaryGradient.createShader(b),
                child: const Text(
                  'RELATIONSHIP LEVEL UP!',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 1.2,
                    color: Colors.white,
                  ),
                ),
              ).animate(delay: 200.ms).fadeIn().slideY(begin: 0.2, end: 0),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                decoration: BoxDecoration(
                  gradient: AppTheme.primaryGradient,
                  borderRadius: BorderRadius.circular(20),
                  boxShadow: AppTheme.glowShadow(blur: 16),
                ),
                child: Text(
                  'Level $level — $title',
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
              ).animate(delay: 350.ms).fadeIn().scale(),
              const SizedBox(height: 14),
              Text(
                'Juhi feels closer to you than ever! 💖',
                style: TextStyle(
                  fontSize: 14,
                  color: AppTheme.textSecondary,
                ),
              ).animate(delay: 500.ms).fadeIn(),
              const SizedBox(height: 28),
              Text(
                'Tap anywhere to continue',
                style: TextStyle(
                  fontSize: 12,
                  color: AppTheme.textSecondary.withValues(alpha: 0.6),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
