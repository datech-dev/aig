import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class XpBar extends StatelessWidget {
  final int level;
  final String title;
  final int percent;
  final int xp;

  const XpBar({
    Key? key,
    required this.level,
    required this.title,
    required this.percent,
    required this.xp,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.cardBg.withOpacity(0.7),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.primaryRose.withOpacity(0.3)),
        boxShadow: [
          BoxShadow(
            color: AppTheme.primaryRose.withOpacity(0.1),
            blurRadius: 10,
            spreadRadius: 1,
          )
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Lvl $level - $title',
                style: const TextStyle(
                  color: AppTheme.textWhite,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Text(
                '$xp XP',
                style: const TextStyle(
                  color: AppTheme.accentCyan,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: Stack(
              children: [
                Container(
                  height: 10,
                  color: Colors.white12,
                ),
                FractionallySizedBox(
                  widthFactor: (percent.clamp(0, 100)) / 100.0,
                  child: Container(
                    height: 10,
                    decoration: const BoxDecoration(
                      gradient: LinearGradient(
                        colors: [AppTheme.primaryRose, AppTheme.accentCyan],
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
