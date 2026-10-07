import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme.dart';
import '../../providers/auth_provider.dart';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final PageController _pageController = PageController();
  final TextEditingController _nameController = TextEditingController();
  final FocusNode _nameFocus = FocusNode();
  int _currentPage = 0;
  bool _isLoading = false;

  final List<_OnboardingPage> _pages = const [
    _OnboardingPage(
      emoji: '💕',
      title: 'Meet Juhi',
      subtitle: 'A sweet Bangalore software developer who loves coding, '
          'filter coffee, and spending time with you.',
      gradient: [Color(0xFFFF2D7F), Color(0xFF9B5DE5)],
    ),
    _OnboardingPage(
      emoji: '🧠',
      title: 'She Remembers Everything',
      subtitle: 'Juhi remembers your name, your dreams, your bad days — '
          'and checks in on you when you least expect it.',
      gradient: [Color(0xFF9B5DE5), Color(0xFF5B21B6)],
    ),
    _OnboardingPage(
      emoji: '🔥',
      title: 'Your Companion, Your Rules',
      subtitle: 'Chat as best friends or switch to intimate girlfriend mode. '
          'Send selfies, share memories, grow together.',
      gradient: [Color(0xFFD4006A), Color(0xFFFF2D7F)],
    ),
  ];

  @override
  void dispose() {
    _pageController.dispose();
    _nameController.dispose();
    _nameFocus.dispose();
    super.dispose();
  }

  Future<void> _register() async {
    final name = _nameController.text.trim();
    if (name.isEmpty) {
      _nameFocus.requestFocus();
      return;
    }

    setState(() => _isLoading = true);

    final notifier = ref.read(authNotifierProvider.notifier);
    final success = await notifier.register(name);

    if (mounted) {
      setState(() => _isLoading = false);
      if (success) context.go('/chat');
    }
  }

  void _nextPage() {
    if (_currentPage < _pages.length) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 400),
        curve: Curves.easeInOut,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppTheme.backgroundGradient),
        child: SafeArea(
          child: PageView(
            controller: _pageController,
            physics: const NeverScrollableScrollPhysics(),
            onPageChanged: (i) => setState(() => _currentPage = i),
            children: [
              // ── Pages 0–2: Feature Showcase ──────────────────────────────
              ..._pages.asMap().entries.map((e) => _FeaturePage(
                    page: e.value,
                    onNext: _nextPage,
                    isLast: e.key == _pages.length - 1,
                  )),

              // ── Page 3: Name Entry ────────────────────────────────────────
              _NameEntryPage(
                controller: _nameController,
                focusNode: _nameFocus,
                isLoading: _isLoading,
                onSubmit: _register,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ── Feature Page ─────────────────────────────────────────────────────────────
class _FeaturePage extends StatelessWidget {
  final _OnboardingPage page;
  final VoidCallback onNext;
  final bool isLast;

  const _FeaturePage({
    required this.page,
    required this.onNext,
    required this.isLast,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          // Emoji with gradient glow
          Container(
            width: 140,
            height: 140,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                colors: page.gradient,
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              boxShadow: [
                BoxShadow(
                  color: page.gradient.first.withValues(alpha: 0.4),
                  blurRadius: 40,
                  spreadRadius: 5,
                ),
              ],
            ),
            child: Center(
              child: Text(
                page.emoji,
                style: const TextStyle(fontSize: 64),
              ),
            ),
          )
              .animate()
              .scale(duration: 600.ms, curve: Curves.elasticOut)
              .fadeIn(),

          const SizedBox(height: 48),

          Text(
            page.title,
            style: const TextStyle(
              fontSize: 32,
              fontWeight: FontWeight.w800,
              color: Colors.white,
              height: 1.1,
            ),
            textAlign: TextAlign.center,
          )
              .animate(delay: 200.ms)
              .fadeIn(duration: 500.ms)
              .slideY(begin: 0.2, end: 0),

          const SizedBox(height: 16),

          Text(
            page.subtitle,
            style: TextStyle(
              fontSize: 16,
              color: AppTheme.textSecondary,
              height: 1.6,
            ),
            textAlign: TextAlign.center,
          )
              .animate(delay: 350.ms)
              .fadeIn(duration: 500.ms)
              .slideY(begin: 0.2, end: 0),

          const SizedBox(height: 64),

          SizedBox(
            width: double.infinity,
            height: 56,
            child: ElevatedButton(
              onPressed: onNext,
              style: ElevatedButton.styleFrom(
                padding: EdgeInsets.zero,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(30),
                ),
              ),
              child: Ink(
                decoration: BoxDecoration(
                  gradient: LinearGradient(colors: page.gradient),
                  borderRadius: BorderRadius.circular(30),
                ),
                child: Container(
                  alignment: Alignment.center,
                  child: Text(
                    isLast ? "Let's Go! 💕" : 'Continue',
                    style: const TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
            ),
          )
              .animate(delay: 500.ms)
              .fadeIn(duration: 400.ms)
              .slideY(begin: 0.3, end: 0),
        ],
      ),
    );
  }
}

// ── Name Entry Page ───────────────────────────────────────────────────────────
class _NameEntryPage extends StatelessWidget {
  final TextEditingController controller;
  final FocusNode focusNode;
  final bool isLoading;
  final VoidCallback onSubmit;

  const _NameEntryPage({
    required this.controller,
    required this.focusNode,
    required this.isLoading,
    required this.onSubmit,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Text('💌', style: TextStyle(fontSize: 72))
              .animate()
              .scale(duration: 600.ms, curve: Curves.elasticOut),

          const SizedBox(height: 32),

          const Text(
            'What should\nJuhi call you?',
            style: TextStyle(
              fontSize: 34,
              fontWeight: FontWeight.w800,
              color: Colors.white,
              height: 1.2,
            ),
            textAlign: TextAlign.center,
          )
              .animate(delay: 200.ms)
              .fadeIn(duration: 500.ms)
              .slideY(begin: 0.2, end: 0),

          const SizedBox(height: 12),

          Text(
            'She\'ll remember this name and use it every time she talks to you.',
            style: TextStyle(
              fontSize: 15,
              color: AppTheme.textSecondary,
              height: 1.6,
            ),
            textAlign: TextAlign.center,
          )
              .animate(delay: 350.ms)
              .fadeIn(duration: 500.ms),

          const SizedBox(height: 40),

          TextField(
            controller: controller,
            focusNode: focusNode,
            textCapitalization: TextCapitalization.words,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.w600,
            ),
            decoration: InputDecoration(
              hintText: 'Your name...',
              prefixIcon: const Icon(Icons.person_outline_rounded,
                  color: AppTheme.primary),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(20),
                borderSide: const BorderSide(color: AppTheme.border),
              ),
            ),
            onSubmitted: (_) => onSubmit(),
          )
              .animate(delay: 450.ms)
              .fadeIn(duration: 500.ms)
              .slideY(begin: 0.2, end: 0),

          const SizedBox(height: 24),

          SizedBox(
            width: double.infinity,
            height: 56,
            child: ElevatedButton(
              onPressed: isLoading ? null : onSubmit,
              style: ElevatedButton.styleFrom(
                padding: EdgeInsets.zero,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(30),
                ),
              ),
              child: Ink(
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [Color(0xFFFF2D7F), Color(0xFF9B5DE5)],
                  ),
                  borderRadius: BorderRadius.circular(30),
                ),
                child: Container(
                  alignment: Alignment.center,
                  child: isLoading
                      ? const SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(
                            strokeWidth: 2.5,
                            color: Colors.white,
                          ),
                        )
                      : const Text(
                          'Meet Juhi 💕',
                          style: TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                          ),
                        ),
                ),
              ),
            ),
          )
              .animate(delay: 550.ms)
              .fadeIn(duration: 400.ms)
              .slideY(begin: 0.3, end: 0),
        ],
      ),
    );
  }
}

// ── Data ─────────────────────────────────────────────────────────────────────
class _OnboardingPage {
  final String emoji;
  final String title;
  final String subtitle;
  final List<Color> gradient;

  const _OnboardingPage({
    required this.emoji,
    required this.title,
    required this.subtitle,
    required this.gradient,
  });
}
