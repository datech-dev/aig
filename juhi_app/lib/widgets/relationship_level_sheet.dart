import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/constants.dart';
import '../core/theme.dart';
import '../providers/profile_provider.dart';

class RelationshipLevelSheet extends ConsumerWidget {
  final int currentLevel;

  const RelationshipLevelSheet({
    super.key,
    required this.currentLevel,
  });

  static Future<void> show(BuildContext context, WidgetRef ref, {int currentLevel = 1}) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) => RelationshipLevelSheet(currentLevel: currentLevel),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final liveProfile = ref.watch(profileProvider).valueOrNull;
    final effectiveCurrentLevel = liveProfile?.level ?? currentLevel;

    return Container(
      constraints: BoxConstraints(
        maxHeight: MediaQuery.of(context).size.height * 0.85,
      ),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
        border: const Border(
          top: BorderSide(color: AppTheme.border, width: 1),
        ),
        boxShadow: AppTheme.glowShadow(blur: 32),
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Drag Handle
              Center(
                child: Container(
                  width: 44,
                  height: 4,
                  decoration: BoxDecoration(
                    color: AppTheme.border,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Sheet Header
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppTheme.primary.withValues(alpha: 0.15),
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(
                      Icons.favorite_rounded,
                      color: AppTheme.primary,
                      size: 20,
                    ),
                  ),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Choose Relationship Stage',
                          style: TextStyle(
                            fontSize: 19,
                            fontWeight: FontWeight.w800,
                            color: Colors.white,
                          ),
                        ),
                        SizedBox(height: 2),
                        Text(
                          'Manually customize how Juhi behaves and connects with you',
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
              const SizedBox(height: 16),

              // Level Cards List
              Flexible(
                child: ListView.separated(
                  shrinkWrap: true,
                  physics: const BouncingScrollPhysics(),
                  itemCount: AppConstants.relationshipLevels.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 10),
                  itemBuilder: (context, index) {
                    final lvl = AppConstants.relationshipLevels[index];
                    final levelNum = lvl['level'] as int;
                    final isCurrent = levelNum == effectiveCurrentLevel;
                    final title = lvl['title'] as String;
                    final emoji = lvl['emoji'] as String;
                    final desc = lvl['description'] as String? ?? '';
                    final affection = lvl['affection'] ?? lvl['xp'];

                    return GestureDetector(
                      onTap: () async {
                        HapticFeedback.mediumImpact();

                        if (isCurrent) {
                          Navigator.pop(context);
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              backgroundColor: AppTheme.surface,
                              behavior: SnackBarBehavior.floating,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(14),
                                side: const BorderSide(color: AppTheme.border),
                              ),
                              content: Text(
                                'Juhi is already in Level $levelNum ($title) stage 💕',
                                style: const TextStyle(color: Colors.white),
                              ),
                            ),
                          );
                          return;
                        }

                        // Capture ScaffoldMessenger before popping modal
                        final messenger = ScaffoldMessenger.of(context);
                        Navigator.pop(context);

                        final success = await ref
                            .read(profileProvider.notifier)
                            .setRelationshipLevel(levelNum);

                        messenger.showSnackBar(
                          SnackBar(
                            backgroundColor: AppTheme.surface,
                            behavior: SnackBarBehavior.floating,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                              side: BorderSide(
                                color: success ? AppTheme.primary : Colors.redAccent,
                                width: 1.2,
                              ),
                            ),
                            content: Row(
                              children: [
                                Text(emoji, style: const TextStyle(fontSize: 22)),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Text(
                                    success
                                        ? 'Relationship stage set to Level $levelNum — $title! Juhi will now talk and behave accordingly 💕'
                                        : 'Failed to update relationship stage. Please check your connection.',
                                    style: const TextStyle(
                                      color: Colors.white,
                                      fontWeight: FontWeight.w600,
                                      fontSize: 13,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                      child: Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: isCurrent
                              ? AppTheme.primary.withValues(alpha: 0.16)
                              : AppTheme.card,
                          borderRadius: BorderRadius.circular(18),
                          border: Border.all(
                            color: isCurrent ? AppTheme.primary : AppTheme.border,
                            width: isCurrent ? 1.5 : 0.8,
                          ),
                          boxShadow: isCurrent ? AppTheme.glowShadow(blur: 16) : null,
                        ),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Emoji Circle
                            Container(
                              width: 44,
                              height: 44,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                gradient: isCurrent
                                    ? AppTheme.primaryGradient
                                    : null,
                                color: isCurrent
                                    ? null
                                    : AppTheme.surface,
                                border: Border.all(
                                  color: isCurrent
                                      ? AppTheme.primary
                                      : AppTheme.border,
                                  width: 1,
                                ),
                              ),
                              child: Center(
                                child: Text(
                                  emoji,
                                  style: const TextStyle(fontSize: 22),
                                ),
                              ),
                            ),
                            const SizedBox(width: 14),

                            // Level Info & Behaviors
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Text(
                                        'Level $levelNum: $title',
                                        style: TextStyle(
                                          fontSize: 15,
                                          fontWeight: FontWeight.w800,
                                          color: isCurrent
                                              ? AppTheme.primary
                                              : Colors.white,
                                        ),
                                      ),
                                      const SizedBox(width: 6),
                                      Text(
                                        '($affection XP)',
                                        style: const TextStyle(
                                          fontSize: 12,
                                          color: AppTheme.textSecondary,
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    desc,
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: isCurrent
                                          ? Colors.white.withValues(alpha: 0.9)
                                          : AppTheme.textSecondary,
                                      height: 1.3,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(width: 10),

                            // State Badge or Action Icon
                            if (isCurrent)
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 8,
                                  vertical: 4,
                                ),
                                decoration: BoxDecoration(
                                  gradient: AppTheme.primaryGradient,
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: const Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(
                                      Icons.check_rounded,
                                      color: Colors.white,
                                      size: 13,
                                    ),
                                    SizedBox(width: 3),
                                    Text(
                                      'ACTIVE',
                                      style: TextStyle(
                                        fontSize: 10,
                                        fontWeight: FontWeight.w800,
                                        color: Colors.white,
                                      ),
                                    ),
                                  ],
                                ),
                              )
                            else
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 10,
                                  vertical: 5,
                                ),
                                decoration: BoxDecoration(
                                  color: AppTheme.surface,
                                  borderRadius: BorderRadius.circular(10),
                                  border: Border.all(
                                    color: AppTheme.border,
                                    width: 0.8,
                                  ),
                                ),
                                child: const Text(
                                  'Select',
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w700,
                                    color: AppTheme.primary,
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
