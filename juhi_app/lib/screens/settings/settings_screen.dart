import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme.dart';
import '../../providers/auth_provider.dart';
import '../../providers/notification_provider.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifState = ref.watch(notificationProvider);

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppTheme.backgroundGradient),
        child: SafeArea(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
                child: ShaderMask(
                  shaderCallback: (b) =>
                      AppTheme.primaryGradient.createShader(b),
                  child: const Text(
                    'Settings ⚙️',
                    style: TextStyle(
                      fontSize: 26,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                    ),
                  ),
                ),
              ).animate().fadeIn(duration: 400.ms),

              Expanded(
                child: ListView(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  children: [
                    // ── Account ──────────────────────────────────────────────
                    _SettingsSection(
                      title: 'Account',
                      items: [
                        _SettingsItem(
                          icon: Icons.person_outline_rounded,
                          title: 'Your Profile',
                          subtitle: 'View relationship stats & Affection 💕',
                          onTap: () => context.go('/profile'),
                        ),
                        _SettingsItem(
                          icon: Icons.psychology_rounded,
                          title: 'Memory Vault',
                          subtitle: 'What Juhi remembers about you',
                          onTap: () => context.go('/memories'),
                        ),
                      ],
                    ).animate(delay: 100.ms).fadeIn().slideY(begin: 0.1, end: 0),

                    const SizedBox(height: 16),

                    // ── Notifications & Companion Care ───────────────────────
                    _SettingsSection(
                      title: 'Companion Notifications',
                      items: [
                        _SettingsToggleItem(
                          icon: Icons.favorite_border_rounded,
                          title: 'Proactive Check-ins',
                          subtitle:
                              'Morning greetings, sweet nothings & late night wishes',
                          value: notifState.proactiveEnabled,
                          onChanged: (val) => ref
                              .read(notificationProvider.notifier)
                              .toggleProactive(val),
                        ),
                        _SettingsToggleItem(
                          icon: Icons.volume_up_rounded,
                          title: 'Sound & Haptics',
                          subtitle:
                              'Play audio chime and gentle vibration for alerts',
                          value: notifState.soundEnabled,
                          onChanged: (val) => ref
                              .read(notificationProvider.notifier)
                              .toggleSound(val),
                        ),
                        _SettingsItem(
                          icon: Icons.mark_chat_unread_rounded,
                          title: 'Send Test Notification',
                          subtitle: 'Preview a spontaneous message from Juhi',
                          trailing: notifState.isSendingTest
                              ? const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    valueColor: AlwaysStoppedAnimation<Color>(
                                        AppTheme.primary),
                                  ),
                                )
                              : null,
                          onTap: () async {
                            await ref
                                .read(notificationProvider.notifier)
                                .sendTestNotification();
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: const Row(
                                    children: [
                                      Text('💌',
                                          style: TextStyle(fontSize: 18)),
                                      SizedBox(width: 8),
                                      Expanded(
                                        child: Text(
                                          'Check-in alert delivered! Check your notification tray.',
                                          style: TextStyle(
                                              color: Colors.white,
                                              fontSize: 13),
                                        ),
                                      ),
                                    ],
                                  ),
                                  backgroundColor: AppTheme.card,
                                  behavior: SnackBarBehavior.floating,
                                  shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(14)),
                                ),
                              );
                            }
                          },
                        ),
                      ],
                    ).animate(delay: 180.ms).fadeIn().slideY(begin: 0.1, end: 0),

                    const SizedBox(height: 16),

                    // ── Subscription ─────────────────────────────────────────
                    _SettingsSection(
                      title: 'Subscription',
                      items: [
                        _SettingsItem(
                          icon: Icons.stars_rounded,
                          title: 'Plans & Pricing',
                          subtitle: 'Unlock unlimited chat and images',
                          onTap: () => context.go('/store'),
                        ),
                      ],
                    ).animate(delay: 240.ms).fadeIn().slideY(begin: 0.1, end: 0),

                    const SizedBox(height: 16),

                    // ── App & Security ───────────────────────────────────────
                    _SettingsSection(
                      title: 'App',
                      items: [
                        _SettingsItem(
                          icon: Icons.info_outline_rounded,
                          title: 'About',
                          subtitle: 'Juhi AI Companion v1.0.0 (Android Ecosystem)',
                          onTap: () {},
                        ),
                        _SettingsItem(
                          icon: Icons.privacy_tip_outlined,
                          title: 'Privacy Policy',
                          subtitle: 'How we keep your intimate messages safe',
                          onTap: () {},
                        ),
                      ],
                    ).animate(delay: 300.ms).fadeIn().slideY(begin: 0.1, end: 0),

                    const SizedBox(height: 32),

                    // ── Logout ───────────────────────────────────────────────
                    Center(
                      child: TextButton.icon(
                        onPressed: () => _confirmLogout(context, ref),
                        icon: const Icon(Icons.logout_rounded,
                            color: Colors.redAccent),
                        label: const Text(
                          'Sign Out',
                          style: TextStyle(
                              color: Colors.redAccent, fontSize: 16),
                        ),
                      ),
                    ).animate(delay: 360.ms).fadeIn(),

                    const SizedBox(height: 24),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _confirmLogout(BuildContext context, WidgetRef ref) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.card,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text('Sign Out?',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700)),
        content: Text(
          'You will be signed out. Your chat history stays safe on the server.',
          style: TextStyle(color: AppTheme.textSecondary, height: 1.5),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text('Cancel',
                style: TextStyle(color: AppTheme.textSecondary)),
          ),
          TextButton(
            onPressed: () async {
              Navigator.pop(ctx);
              await ref.read(authNotifierProvider.notifier).logout();
              if (context.mounted) context.go('/onboarding');
            },
            child: const Text('Sign Out',
                style: TextStyle(color: Colors.redAccent)),
          ),
        ],
      ),
    );
  }
}

class _SettingsSection extends StatelessWidget {
  final String title;
  final List<Widget> items;

  const _SettingsSection({required this.title, required this.items});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 8),
          child: Text(
            title.toUpperCase(),
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              color: AppTheme.textSecondary,
              letterSpacing: 1.2,
            ),
          ),
        ),
        Container(
          decoration: BoxDecoration(
            color: AppTheme.card,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: AppTheme.border, width: 0.5),
          ),
          child: Column(
            children: items
                .asMap()
                .entries
                .map((e) => Column(
                      children: [
                        e.value,
                        if (e.key < items.length - 1)
                          const Divider(
                            color: AppTheme.border,
                            thickness: 0.5,
                            height: 0,
                            indent: 56,
                          ),
                      ],
                    ))
                .toList(),
          ),
        ),
      ],
    );
  }
}

class _SettingsItem extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final Widget? trailing;

  const _SettingsItem({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          child: Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: AppTheme.primary.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: AppTheme.primary, size: 20),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                      ),
                    ),
                    Text(
                      subtitle,
                      style: TextStyle(
                        fontSize: 12,
                        color: AppTheme.textSecondary,
                      ),
                    ),
                  ],
                ),
              ),
              trailing ??
                  Icon(Icons.chevron_right_rounded,
                      color: AppTheme.textSecondary, size: 20),
            ],
          ),
        ),
      ),
    );
  }
}

class _SettingsToggleItem extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;

  const _SettingsToggleItem({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.value,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 11),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: AppTheme.primary.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: AppTheme.primary, size: 20),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
                Text(
                  subtitle,
                  style: TextStyle(
                    fontSize: 12,
                    color: AppTheme.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          Switch.adaptive(
            value: value,
            activeThumbColor: AppTheme.primary,
            activeTrackColor: AppTheme.primary.withValues(alpha: 0.35),
            inactiveThumbColor: Colors.grey.shade400,
            inactiveTrackColor: Colors.white12,
            onChanged: onChanged,
          ),
        ],
      ),
    );
  }
}
