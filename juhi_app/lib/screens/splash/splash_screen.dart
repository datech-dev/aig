import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme.dart';
import '../../providers/auth_provider.dart';

class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _pulseController;
  Timer? _navTimer;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);

    // Navigate after 2.5 seconds
    _navTimer = Timer(const Duration(milliseconds: 2800), () {
      if (mounted) _navigate();
    });
  }

  void _navigate() {
    final authState = ref.read(authStateProvider);
    authState.when(
      data: (isLoggedIn) {
        if (isLoggedIn) {
          context.go('/chat');
        } else {
          context.go('/onboarding');
        }
      },
      loading: () {
        _navTimer = Timer(const Duration(milliseconds: 500), () {
          if (mounted) _navigate();
        });
      },
      error: (_, __) => context.go('/onboarding'),
    );
  }

  @override
  void dispose() {
    _navTimer?.cancel();
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppTheme.backgroundGradient),
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              // ── Pulsing Glow Avatar ──────────────────────────────────────
              AnimatedBuilder(
                animation: _pulseController,
                builder: (context, child) {
                  return Container(
                    width: 140 + (_pulseController.value * 10),
                    height: 140 + (_pulseController.value * 10),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: AppTheme.primary.withValues(
                            alpha: 0.3 + _pulseController.value * 0.3,
                          ),
                          blurRadius: 40 + _pulseController.value * 20,
                          spreadRadius: 5 + _pulseController.value * 5,
                        ),
                      ],
                    ),
                    child: child,
                  );
                },
                child: Container(
                  width: 140,
                  height: 140,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: const LinearGradient(
                      colors: [Color(0xFF2A0050), Color(0xFF1A0035)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    border: Border.all(
                      color: AppTheme.primary.withValues(alpha: 0.6),
                      width: 2.5,
                    ),
                  ),
                  child: const ClipOval(
                    child: _JuhiAvatarPlaceholder(),
                  ),
                ),
              )
                  .animate()
                  .scale(
                    begin: const Offset(0.5, 0.5),
                    end: const Offset(1.0, 1.0),
                    duration: 800.ms,
                    curve: Curves.elasticOut,
                  ),

              const SizedBox(height: 32),

              // ── App Name ─────────────────────────────────────────────────
              ShaderMask(
                shaderCallback: (bounds) =>
                    AppTheme.primaryGradient.createShader(bounds),
                child: const Text(
                  'Juhi',
                  style: TextStyle(
                    fontSize: 52,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                    letterSpacing: -1,
                  ),
                ),
              )
                  .animate(delay: 300.ms)
                  .fadeIn(duration: 600.ms)
                  .slideY(begin: 0.3, end: 0),

              const SizedBox(height: 8),

              // ── Tagline ───────────────────────────────────────────────────
              Text(
                'Your AI Companion 💕',
                style: TextStyle(
                  fontSize: 16,
                  color: AppTheme.textSecondary,
                  fontWeight: FontWeight.w500,
                  letterSpacing: 0.5,
                ),
              )
                  .animate(delay: 500.ms)
                  .fadeIn(duration: 600.ms)
                  .slideY(begin: 0.2, end: 0),

              const SizedBox(height: 80),

              // ── Loading dots ──────────────────────────────────────────────
              _LoadingDots()
                  .animate(delay: 800.ms)
                  .fadeIn(duration: 400.ms),
            ],
          ),
        ),
      ),
    );
  }
}

class _JuhiAvatarPlaceholder extends StatelessWidget {
  const _JuhiAvatarPlaceholder();

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      'assets/images/juhi_avatar.png',
      fit: BoxFit.cover,
      errorBuilder: (_, __, ___) => Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFF3D0070), Color(0xFF200040)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: const Center(
          child: Text('💕', style: TextStyle(fontSize: 56)),
        ),
      ),
    );
  }
}

class _LoadingDots extends StatefulWidget {
  @override
  State<_LoadingDots> createState() => _LoadingDotsState();
}

class _LoadingDotsState extends State<_LoadingDots>
    with TickerProviderStateMixin {
  late List<AnimationController> _controllers;
  final List<Timer> _timers = [];

  @override
  void initState() {
    super.initState();
    _controllers = List.generate(3, (i) {
      final c = AnimationController(
        vsync: this,
        duration: const Duration(milliseconds: 600),
      );
      _timers.add(Timer(Duration(milliseconds: i * 200), () {
        if (mounted) c.repeat(reverse: true);
      }));
      return c;
    });
  }

  @override
  void dispose() {
    for (final t in _timers) {
      t.cancel();
    }
    for (final c in _controllers) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(3, (i) {
        return AnimatedBuilder(
          animation: _controllers[i],
          builder: (context, _) {
            return Container(
              margin: const EdgeInsets.symmetric(horizontal: 4),
              width: 8,
              height: 8 + _controllers[i].value * 4,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppTheme.primary.withValues(
                  alpha: 0.5 + _controllers[i].value * 0.5,
                ),
              ),
            );
          },
        );
      }),
    );
  }
}
