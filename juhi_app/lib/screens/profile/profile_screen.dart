import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme.dart';
import '../../providers/profile_provider.dart';
import '../../core/constants.dart';
import '../../data/local_storage.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profileState = ref.watch(profileProvider);

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppTheme.backgroundGradient),
        child: profileState.isLoading
            ? const Center(
                child: CircularProgressIndicator(color: AppTheme.primary))
            : profileState.valueOrNull == null
                ? Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text(
                          'Unable to load profile',
                          style: TextStyle(color: Colors.white, fontSize: 16),
                        ),
                        const SizedBox(height: 12),
                        ElevatedButton(
                          onPressed: () =>
                              ref.read(profileProvider.notifier).refresh(),
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  )
                : RefreshIndicator(
                    color: AppTheme.primary,
                    backgroundColor: AppTheme.surface,
                    onRefresh: () =>
                        ref.read(profileProvider.notifier).refresh(),
                    child: _ProfileContent(profile: profileState.value!),
                  ),
      ),
    );
  }
}

class _ProfileContent extends ConsumerWidget {
  final dynamic profile;

  const _ProfileContent({required this.profile});

  void _showEditNicknameDialog(BuildContext context, WidgetRef ref) {
    final userController =
        TextEditingController(text: profile.userNickname as String);

    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        backgroundColor: Colors.transparent,
        child: Container(
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: AppTheme.card,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: AppTheme.primary, width: 1.2),
            boxShadow: AppTheme.glowShadow(blur: 24),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppTheme.primary.withValues(alpha: 0.15),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.edit_rounded,
                        color: AppTheme.primary, size: 20),
                  ),
                  const SizedBox(width: 12),
                  const Text(
                    'What should Juhi call you?',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              TextField(
                controller: userController,
                autofocus: true,
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: 'Enter your pet name or nickname...',
                  hintStyle: TextStyle(color: AppTheme.textSecondary),
                  filled: true,
                  fillColor: AppTheme.surface,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide:
                        const BorderSide(color: AppTheme.border, width: 1),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide:
                        const BorderSide(color: AppTheme.primary, width: 1.5),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.pop(ctx),
                    child: Text('Cancel',
                        style: TextStyle(color: AppTheme.textSecondary)),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton(
                    onPressed: () async {
                      final newNick = userController.text.trim();
                      if (newNick.isNotEmpty) {
                        await LocalStorage.saveUserName(newNick);
                        await ref.read(profileProvider.notifier).refresh();
                        HapticFeedback.lightImpact();
                        if (context.mounted) Navigator.pop(ctx);
                      }
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primary,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14)),
                    ),
                    child: const Text('Save Nickname'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final levelInfo = AppConstants.relationshipLevels.firstWhere(
      (l) => l['level'] == profile.level,
      orElse: () => AppConstants.relationshipLevels.first,
    );

    final affection = profile.affection as int;
    final affectionPercent = profile.affectionPercent as int;

    return CustomScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      slivers: [
        // ── Header Hero with Glowing Portrait ──────────────────────────────
        SliverAppBar(
          expandedHeight: 250,
          pinned: true,
          backgroundColor: AppTheme.surface,
          flexibleSpace: FlexibleSpaceBar(
            background: Container(
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [Color(0xFF2A0050), Color(0xFF0A0010)],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const SizedBox(height: 36),
                  // Glow avatar
                  Container(
                    width: 104,
                    height: 104,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: AppTheme.primaryGradient,
                      boxShadow: AppTheme.glowShadow(blur: 26),
                    ),
                    child: ClipOval(
                      child: Image.asset(
                        'assets/images/juhi_avatar.png',
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => const Center(
                          child: Text('💕', style: TextStyle(fontSize: 48)),
                        ),
                      ),
                    ),
                  ).animate().scale(duration: 600.ms, curve: Curves.elasticOut),
                  const SizedBox(height: 12),
                  Text(
                    profile.partnerName as String,
                    style: const TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    profile.partnerTagline as String,
                    style: TextStyle(
                      fontSize: 13,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: profile.isIntimateMode as bool
                          ? AppTheme.primary.withValues(alpha: 0.2)
                          : AppTheme.card,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(
                        color: profile.isIntimateMode as bool
                            ? AppTheme.primary
                            : AppTheme.border,
                        width: 0.8,
                      ),
                    ),
                    child: Text(
                      profile.isIntimateMode as bool
                          ? '🔥 Intimate Girlfriend Mode'
                          : '🌸 Caring Best Friend Mode',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: profile.isIntimateMode as bool
                            ? AppTheme.primary
                            : Colors.white,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),

        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ── Affection Meter Card (Replaced XP) ──────────────────────
                _SectionCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(
                            children: [
                              Text(
                                levelInfo['emoji'] as String,
                                style: const TextStyle(fontSize: 26),
                              ),
                              const SizedBox(width: 10),
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Level ${profile.level} — ${profile.levelTitle}',
                                    style: const TextStyle(
                                      fontSize: 17,
                                      fontWeight: FontWeight.w800,
                                      color: Colors.white,
                                    ),
                                  ),
                                  const SizedBox(height: 1),
                                  Text(
                                    '$affection Affection Points 💕',
                                    style: const TextStyle(
                                      fontSize: 13,
                                      color: AppTheme.primary,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              gradient: AppTheme.primaryGradient,
                              borderRadius: BorderRadius.circular(16),
                            ),
                            child: Text(
                              '$affectionPercent%',
                              style: const TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w800,
                                color: Colors.white,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Animated Gradient Progress Bar
                      ClipRRect(
                        borderRadius: BorderRadius.circular(10),
                        child: Stack(
                          children: [
                            Container(
                              height: 10,
                              color: AppTheme.border,
                            ),
                            FractionallySizedBox(
                              widthFactor: (affectionPercent / 100).clamp(0.05, 1.0),
                              child: Container(
                                height: 10,
                                decoration: BoxDecoration(
                                  gradient: AppTheme.primaryGradient,
                                  boxShadow: AppTheme.glowShadow(blur: 8),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 8),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Earn +10 Affection on every message',
                            style: TextStyle(
                              fontSize: 11,
                              color: AppTheme.textSecondary,
                            ),
                          ),
                          Text(
                            'Next Milestone ✨',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: AppTheme.textSecondary,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ).animate(delay: 100.ms).fadeIn().slideY(begin: 0.15, end: 0),

                const SizedBox(height: 18),

                // ── Interactive Stats Grid ─────────────────────────────────
                Row(
                  children: [
                    Expanded(
                      child: GestureDetector(
                        onTap: () => context.go('/store'),
                        child: _StatCard(
                          icon: '🖼️',
                          value: '${profile.imageCredits}',
                          label: 'Photo Credits',
                          actionLabel: 'Get more +',
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: GestureDetector(
                        onTap: () => context.go('/memories'),
                        child: _StatCard(
                          icon: '🧠',
                          value: '${profile.memoryCount}',
                          label: 'Memories',
                          actionLabel: 'View vault →',
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: GestureDetector(
                        onTap: () => context.go('/store'),
                        child: _StatCard(
                          icon: '💬',
                          value: profile.isSubscribed as bool
                              ? '∞'
                              : '${profile.remainingFreeMessages}',
                          label: profile.isSubscribed as bool
                              ? 'Unlimited'
                              : 'Free Left',
                          actionLabel: profile.isSubscribed as bool
                              ? 'Active 👑'
                              : 'Upgrade',
                        ),
                      ),
                    ),
                  ],
                ).animate(delay: 200.ms).fadeIn(),

                const SizedBox(height: 18),

                // ── Relationship Journey Timeline ──────────────────────────
                const Text(
                  'Relationship Journey',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 10),
                _RelationshipJourneyPath(currentLevel: profile.level as int),

                const SizedBox(height: 18),

                // ── Nicknames Section (Editable) ───────────────────────────
                _SectionCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'Special Nicknames',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w700,
                              color: Colors.white,
                            ),
                          ),
                          GestureDetector(
                            onTap: () => _showEditNicknameDialog(context, ref),
                            child: Row(
                              children: [
                                const Icon(Icons.edit_rounded,
                                    size: 14, color: AppTheme.primary),
                                const SizedBox(width: 4),
                                Text(
                                  'Edit',
                                  style: TextStyle(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w700,
                                    color: AppTheme.primary,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),
                      Row(
                        children: [
                          Expanded(
                            child: Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: AppTheme.surface,
                                borderRadius: BorderRadius.circular(14),
                                border: Border.all(
                                    color: AppTheme.border, width: 0.6),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Juhi calls you',
                                    style: TextStyle(
                                      fontSize: 11,
                                      color: AppTheme.textSecondary,
                                    ),
                                  ),
                                  const SizedBox(height: 3),
                                  Text(
                                    profile.userNickname as String,
                                    style: const TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.w700,
                                      color: Colors.white,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                          const Padding(
                            padding: EdgeInsets.symmetric(horizontal: 10),
                            child: Text('💖', style: TextStyle(fontSize: 20)),
                          ),
                          Expanded(
                            child: Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: AppTheme.surface,
                                borderRadius: BorderRadius.circular(14),
                                border: Border.all(
                                    color: AppTheme.border, width: 0.6),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Her name',
                                    style: TextStyle(
                                      fontSize: 11,
                                      color: AppTheme.textSecondary,
                                    ),
                                  ),
                                  const SizedBox(height: 3),
                                  Text(
                                    profile.aiNickname as String,
                                    style: const TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.w700,
                                      color: Colors.white,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ).animate(delay: 300.ms).fadeIn(),

                const SizedBox(height: 18),

                // ── Subscription Card ──────────────────────────────────────
                GestureDetector(
                  onTap: () => context.go('/store'),
                  child: _SectionCard(
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: profile.isSubscribed as bool
                                ? AppTheme.primary.withValues(alpha: 0.18)
                                : AppTheme.border.withValues(alpha: 0.4),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Icon(
                            profile.isSubscribed as bool
                                ? Icons.verified_rounded
                                : Icons.lock_outline_rounded,
                            color: profile.isSubscribed as bool
                                ? AppTheme.primary
                                : AppTheme.textSecondary,
                            size: 26,
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                profile.isSubscribed as bool
                                    ? 'Unlimited Membership Active 👑'
                                    : 'Free Trial Plan',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w700,
                                  color: profile.isSubscribed as bool
                                      ? AppTheme.primary
                                      : Colors.white,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                profile.isSubscribed as bool
                                    ? '24/7 Unlimited Intimate chats & selfies'
                                    : '${profile.remainingFreeMessages} messages remaining today',
                                style: TextStyle(
                                  fontSize: 13,
                                  color: AppTheme.textSecondary,
                                ),
                              ),
                            ],
                          ),
                        ),
                        if (!(profile.isSubscribed as bool))
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 12, vertical: 6),
                            decoration: BoxDecoration(
                              gradient: AppTheme.primaryGradient,
                              borderRadius: BorderRadius.circular(16),
                            ),
                            child: const Text(
                              'Upgrade',
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w700,
                                color: Colors.white,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ).animate(delay: 400.ms).fadeIn(),

                const SizedBox(height: 24),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

// ── Relationship Journey Visual Path ──────────────────────────────────────────
class _RelationshipJourneyPath extends StatelessWidget {
  final int currentLevel;

  const _RelationshipJourneyPath({required this.currentLevel});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.card,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.border, width: 0.6),
        boxShadow: AppTheme.cardShadow,
      ),
      child: Column(
        children: AppConstants.relationshipLevels.map((lvl) {
          final levelNum = lvl['level'] as int;
          final isUnlocked = levelNum <= currentLevel;
          final isCurrent = levelNum == currentLevel;
          final reqAffection = lvl['affection'] ?? lvl['xp'];

          return Container(
            margin: const EdgeInsets.symmetric(vertical: 4),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: isCurrent
                  ? AppTheme.primary.withValues(alpha: 0.15)
                  : Colors.transparent,
              borderRadius: BorderRadius.circular(14),
              border: isCurrent
                  ? Border.all(color: AppTheme.primary, width: 1.2)
                  : null,
            ),
            child: Row(
              children: [
                // Milestone icon / checkmark
                Container(
                  width: 34,
                  height: 34,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: isCurrent
                        ? AppTheme.primary
                        : isUnlocked
                            ? AppTheme.surface
                            : AppTheme.border.withValues(alpha: 0.4),
                    border: Border.all(
                      color: isUnlocked ? AppTheme.primary : AppTheme.border,
                      width: 1,
                    ),
                  ),
                  child: Center(
                    child: isUnlocked
                        ? Text(lvl['emoji'] as String,
                            style: const TextStyle(fontSize: 16))
                        : const Icon(Icons.lock_rounded,
                            size: 14, color: Color(0xFF888888)),
                  ),
                ),

                const SizedBox(width: 12),

                // Level title and affection requirements
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Text(
                            'Level $levelNum — ${lvl['title']}',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight:
                                  isCurrent ? FontWeight.w800 : FontWeight.w600,
                              color: isUnlocked
                                  ? Colors.white
                                  : AppTheme.textSecondary.withValues(alpha: 0.6),
                            ),
                          ),
                          if (isCurrent) ...[
                            const SizedBox(width: 6),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 6, vertical: 2),
                              decoration: BoxDecoration(
                                gradient: AppTheme.primaryGradient,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: const Text(
                                'CURRENT',
                                style: TextStyle(
                                  fontSize: 9,
                                  fontWeight: FontWeight.w800,
                                  color: Colors.white,
                                ),
                              ),
                            ),
                          ],
                        ],
                      ),
                      Text(
                        '$reqAffection Affection required',
                        style: TextStyle(
                          fontSize: 12,
                          color: isCurrent
                              ? AppTheme.primary
                              : AppTheme.textSecondary.withValues(alpha: 0.7),
                        ),
                      ),
                    ],
                  ),
                ),

                // Status check or lock
                if (isUnlocked)
                  const Icon(Icons.check_circle_rounded,
                      color: AppTheme.primary, size: 18)
                else
                  Text(
                    'Locked',
                    style: TextStyle(
                      fontSize: 12,
                      color: AppTheme.textSecondary.withValues(alpha: 0.5),
                    ),
                  ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  final Widget child;

  const _SectionCard({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppTheme.card,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.border, width: 0.6),
        boxShadow: AppTheme.cardShadow,
      ),
      child: child,
    );
  }
}

class _StatCard extends StatelessWidget {
  final String icon;
  final String value;
  final String label;
  final String actionLabel;

  const _StatCard({
    required this.icon,
    required this.value,
    required this.label,
    required this.actionLabel,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 8),
      decoration: BoxDecoration(
        color: AppTheme.card,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border, width: 0.6),
      ),
      child: Column(
        children: [
          Text(icon, style: const TextStyle(fontSize: 22)),
          const SizedBox(height: 4),
          Text(
            value,
            style: const TextStyle(
              fontSize: 19,
              fontWeight: FontWeight.w800,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: TextStyle(fontSize: 11, color: AppTheme.textSecondary),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 4),
          Text(
            actionLabel,
            style: const TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w700,
              color: AppTheme.primary,
            ),
          ),
        ],
      ),
    );
  }
}
