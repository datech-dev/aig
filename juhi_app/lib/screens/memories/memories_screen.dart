import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/theme.dart';
import '../../data/api_service.dart';
import '../../data/local_storage.dart';
import '../../models/memory_item.dart';

final _memoriesProvider = FutureProvider<List<MemoryItem>>((ref) async {
  final userId = await LocalStorage.getUserId();
  if (userId == null) return [];
  final data = await apiService.getMemories(userId);
  if (data['success'] == true) {
    final rawList = List<String>.from(data['memories'] ?? []);
    return rawList.map((str) => MemoryItem.fromText(str)).toList();
  }
  return [];
});

class MemoriesScreen extends ConsumerStatefulWidget {
  const MemoriesScreen({super.key});

  @override
  ConsumerState<MemoriesScreen> createState() => _MemoriesScreenState();
}

class _MemoriesScreenState extends ConsumerState<MemoriesScreen> {
  String _selectedCategory = 'All';
  String _searchQuery = '';
  final TextEditingController _searchController = TextEditingController();

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _confirmClear(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.card,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.redAccent.withValues(alpha: 0.15),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.delete_forever_rounded,
                  color: Colors.redAccent, size: 22),
            ),
            const SizedBox(width: 12),
            const Text(
              'Clear Memory Vault?',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w700,
                fontSize: 18,
              ),
            ),
          ],
        ),
        content: Text(
          'Juhi will forget all personal facts, habits, and preferences she learned about you. This action is permanent.',
          style: TextStyle(
            color: AppTheme.textSecondary,
            fontSize: 14,
            height: 1.45,
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: Text(
              'Keep Memories',
              style: TextStyle(color: AppTheme.textSecondary),
            ),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.pop(ctx);
              final userId = await LocalStorage.getUserId();
              if (userId != null) {
                await apiService.clearMemories(userId);
                ref.invalidate(_memoriesProvider);
                HapticFeedback.mediumImpact();
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: const Text('Memory vault reset successfully.'),
                      backgroundColor: AppTheme.surface,
                      behavior: SnackBarBehavior.floating,
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                    ),
                  );
                }
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.redAccent,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12)),
            ),
            child: const Text('Clear All'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final memoriesState = ref.watch(_memoriesProvider);
    final allMemories = memoriesState.valueOrNull ?? [];

    final filteredMemories = allMemories.where((m) {
      final matchesCat =
          _selectedCategory == 'All' || m.category == _selectedCategory;
      final matchesSearch = _searchQuery.isEmpty ||
          m.text.toLowerCase().contains(_searchQuery.toLowerCase());
      return matchesCat && matchesSearch;
    }).toList();

    const categories = [
      {'name': 'All', 'icon': '✨'},
      {'name': 'Personal', 'icon': '🌸'},
      {'name': 'Preferences', 'icon': '☕'},
      {'name': 'Career', 'icon': '💼'},
      {'name': 'Routine', 'icon': '⏰'},
      {'name': 'Romance', 'icon': '💖'},
    ];

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppTheme.backgroundGradient),
        child: SafeArea(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Header Bar ───────────────────────────────────────────────
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 20, 20, 10),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              ShaderMask(
                                shaderCallback: (b) =>
                                    AppTheme.primaryGradient.createShader(b),
                                child: const Text(
                                  'Memory Vault 🧠',
                                  style: TextStyle(
                                    fontSize: 26,
                                    fontWeight: FontWeight.w800,
                                    color: Colors.white,
                                  ),
                                ),
                              ),
                              if (allMemories.isNotEmpty) ...[
                                const SizedBox(width: 8),
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 8, vertical: 2),
                                  decoration: BoxDecoration(
                                    gradient: AppTheme.primaryGradient,
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  child: Text(
                                    '${allMemories.length}',
                                    style: const TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w800,
                                      color: Colors.white,
                                    ),
                                  ),
                                ),
                              ],
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Everything Juhi lovingly remembers about you',
                            style: TextStyle(
                              fontSize: 13,
                              color: AppTheme.textSecondary,
                            ),
                          ),
                        ],
                      ),
                    ),
                    if (allMemories.isNotEmpty)
                      IconButton(
                        onPressed: () => _confirmClear(context),
                        icon: const Icon(Icons.delete_sweep_rounded),
                        color: Colors.redAccent.withValues(alpha: 0.8),
                        tooltip: 'Clear vault',
                      ),
                  ],
                ),
              ),

              // ── Search Bar ───────────────────────────────────────────────
              if (allMemories.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 6),
                  child: Container(
                    decoration: BoxDecoration(
                      color: AppTheme.card,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppTheme.border, width: 0.8),
                    ),
                    child: TextField(
                      controller: _searchController,
                      onChanged: (val) => setState(() => _searchQuery = val),
                      style: const TextStyle(color: Colors.white, fontSize: 14),
                      decoration: InputDecoration(
                        hintText: 'Search memories (coffee, work, dreams)...',
                        hintStyle: TextStyle(
                          color: AppTheme.textSecondary.withValues(alpha: 0.7),
                          fontSize: 13,
                        ),
                        prefixIcon: const Icon(Icons.search_rounded,
                            color: AppTheme.primary, size: 20),
                        suffixIcon: _searchQuery.isNotEmpty
                            ? IconButton(
                                icon: const Icon(Icons.close_rounded, size: 18),
                                color: AppTheme.textSecondary,
                                onPressed: () {
                                  _searchController.clear();
                                  setState(() => _searchQuery = '');
                                },
                              )
                            : null,
                        border: InputBorder.none,
                        contentPadding:
                            const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ),
                  ),
                ),

              // ── Category Filter Chips ────────────────────────────────────
              if (allMemories.isNotEmpty)
                Container(
                  height: 46,
                  margin: const EdgeInsets.only(top: 8, bottom: 8),
                  child: ListView.builder(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemCount: categories.length,
                    itemBuilder: (context, i) {
                      final cat = categories[i];
                      final isSelected = _selectedCategory == cat['name'];

                      return GestureDetector(
                        onTap: () {
                          HapticFeedback.selectionClick();
                          setState(() => _selectedCategory = cat['name']!);
                        },
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 200),
                          margin: const EdgeInsets.symmetric(horizontal: 4),
                          padding: const EdgeInsets.symmetric(
                              horizontal: 14, vertical: 8),
                          decoration: BoxDecoration(
                            gradient: isSelected ? AppTheme.primaryGradient : null,
                            color: isSelected ? null : AppTheme.card,
                            borderRadius: BorderRadius.circular(20),
                            border: isSelected
                                ? null
                                : Border.all(
                                    color: AppTheme.border, width: 0.8),
                            boxShadow: isSelected
                                ? AppTheme.glowShadow(blur: 8)
                                : null,
                          ),
                          child: Row(
                            children: [
                              Text(cat['icon']!,
                                  style: const TextStyle(fontSize: 14)),
                              const SizedBox(width: 6),
                              Text(
                                cat['name']!,
                                style: TextStyle(
                                  fontSize: 12,
                                  fontWeight: isSelected
                                      ? FontWeight.w700
                                      : FontWeight.w500,
                                  color: Colors.white,
                                ),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),

              // ── Memory List / Empty State ────────────────────────────────
              Expanded(
                child: RefreshIndicator(
                  color: AppTheme.primary,
                  backgroundColor: AppTheme.surface,
                  onRefresh: () async => ref.refresh(_memoriesProvider),
                  child: memoriesState.isLoading
                      ? const Center(
                          child: CircularProgressIndicator(
                              color: AppTheme.primary))
                      : allMemories.isEmpty
                          ? _EmptyMemories()
                          : filteredMemories.isEmpty
                              ? Center(
                                  child: Column(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      const Text('🔍',
                                          style: TextStyle(fontSize: 48)),
                                      const SizedBox(height: 12),
                                      const Text(
                                        'No matching memories found',
                                        style: TextStyle(
                                            color: Colors.white, fontSize: 16),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        'Try a different search word or category filter',
                                        style: TextStyle(
                                          color: AppTheme.textSecondary,
                                          fontSize: 13,
                                        ),
                                      ),
                                    ],
                                  ),
                                )
                              : ListView.builder(
                                  padding: const EdgeInsets.fromLTRB(
                                      20, 8, 20, 20),
                                  itemCount: filteredMemories.length,
                                  itemBuilder: (context, i) {
                                    final item = filteredMemories[i];
                                    return _MemoryCard(
                                      memory: item,
                                      index: i,
                                    )
                                        .animate(
                                            delay:
                                                Duration(milliseconds: i * 40))
                                        .fadeIn(duration: 250.ms)
                                        .slideX(begin: 0.05, end: 0);
                                  },
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

// ── Memory Card Widget ────────────────────────────────────────────────────────
class _MemoryCard extends StatelessWidget {
  final MemoryItem memory;
  final int index;

  const _MemoryCard({required this.memory, required this.index});

  void _copyToClipboard(BuildContext context) {
    Clipboard.setData(ClipboardData(text: memory.text));
    HapticFeedback.lightImpact();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text('Memory copied to clipboard ✨'),
        duration: const Duration(seconds: 1),
        behavior: SnackBarBehavior.floating,
        backgroundColor: AppTheme.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppTheme.card,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: AppTheme.border, width: 0.8),
        boxShadow: AppTheme.cardShadow,
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: () => _copyToClipboard(context),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Category Tag Header
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: AppTheme.primary.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: AppTheme.primary.withValues(alpha: 0.3),
                          width: 0.8,
                        ),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(memory.icon, style: const TextStyle(fontSize: 13)),
                          const SizedBox(width: 5),
                          Text(
                            memory.category,
                            style: const TextStyle(
                              color: AppTheme.primary,
                              fontSize: 11,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ),
                    Icon(
                      Icons.copy_rounded,
                      size: 14,
                      color: AppTheme.textSecondary.withValues(alpha: 0.6),
                    ),
                  ],
                ),
                const SizedBox(height: 10),

                // Memory Content
                Text(
                  memory.text,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14.5,
                    height: 1.5,
                    fontWeight: FontWeight.w400,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── Empty Memories Placeholder ────────────────────────────────────────────────
class _EmptyMemories extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 100,
              height: 100,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: AppTheme.primaryGradient,
                boxShadow: AppTheme.glowShadow(blur: 24),
              ),
              child: const Center(
                child: Text('🧠', style: TextStyle(fontSize: 48)),
              ),
            ).animate().scale(duration: 600.ms, curve: Curves.elasticOut),
            const SizedBox(height: 24),
            const Text(
              "Juhi is listening...",
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w800,
                color: Colors.white,
              ),
              textAlign: TextAlign.center,
            ).animate(delay: 200.ms).fadeIn(),
            const SizedBox(height: 8),
            Text(
              "As you chat, Juhi automatically extracts and securely stores details about your preferences, work, and memorable moments.",
              style: TextStyle(
                fontSize: 14,
                color: AppTheme.textSecondary,
                height: 1.45,
              ),
              textAlign: TextAlign.center,
            ).animate(delay: 350.ms).fadeIn(),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: () => context.go('/chat'),
              icon: const Icon(Icons.chat_bubble_rounded, size: 18),
              label: const Text('Start Chatting with Juhi 💖'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primary,
                foregroundColor: Colors.white,
                padding:
                    const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(20),
                ),
              ),
            ).animate(delay: 500.ms).fadeIn().scale(),
          ],
        ),
      ),
    );
  }
}
