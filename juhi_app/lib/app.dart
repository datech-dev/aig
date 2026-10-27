import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/theme.dart';
import 'core/router.dart';

import 'services/analytics_service.dart';

class JuhiApp extends ConsumerStatefulWidget {
  const JuhiApp({super.key});

  @override
  ConsumerState<JuhiApp> createState() => _JuhiAppState();
}

class _JuhiAppState extends ConsumerState<JuhiApp> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    analyticsService.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      analyticsService.logAppResume();
    } else if (state == AppLifecycleState.paused || state == AppLifecycleState.detached) {
      analyticsService.logAppPause();
    }
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      title: 'Juhi AI',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      routerConfig: router,
    );
  }
}

