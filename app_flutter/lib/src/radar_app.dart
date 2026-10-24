import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'alert_center_page.dart';
import 'api_client.dart';
import 'profitability_simulator_page.dart';

const _ink = Color(0xFF132A26);
const _green = Color(0xFF126B55);
const _canvas = Color(0xFFF5F7F4);

const _sessionStorage = FlutterSecureStorage();
const _sessionTokenKey = 'radar_session_access_token';

class RadarApp extends StatelessWidget {
  const RadarApp({this.api, super.key});

  final ApiClient? api;

  @override
  Widget build(BuildContext context) => MaterialApp(
        navigatorKey: _appNavigatorKey,
        title: 'Radar Leilão',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: _green),
          scaffoldBackgroundColor: _canvas,
          useMaterial3: true,
          appBarTheme: const AppBarTheme(
              backgroundColor: _canvas, foregroundColor: _ink),
          inputDecorationTheme: InputDecorationTheme(
            filled: true,
            fillColor: Colors.white,
            border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: BorderSide.none),
            enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: const BorderSide(color: Color(0xFFE5EAE6))),
            focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(16),
                borderSide: const BorderSide(color: _green, width: 1.5)),
          ),
        ),
        home: _SessionGate(api: api),
      );
}

final _appNavigatorKey = GlobalKey<NavigatorState>();

class _SessionGate extends StatefulWidget {
  const _SessionGate({this.api});

  final ApiClient? api;

  @override
  State<_SessionGate> createState() => _SessionGateState();
}

class _SessionGateState extends State<_SessionGate> {
  late final ApiClient _api = widget.api ?? ApiClient();
  String? _token;
  String? _userId;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _restoreSession();
  }

  Future<void> _restoreSession() async {
    try {
      final token = await _sessionStorage.read(key: _sessionTokenKey);
      if (token != null && token.isNotEmpty) {
        final user = await _api.getCurrentUser(token);
        final id = user['id'];
        if (id != null && '$id'.trim().isNotEmpty) {
          _token = token;
          _userId = '$id';
          _installUnauthorizedHandler();
        } else {
          await _sessionStorage.delete(key: _sessionTokenKey);
        }
      }
    } catch (_) {
      // A storage/API failure must still allow access to the login screen.
      try {
        await _sessionStorage.delete(key: _sessionTokenKey);
      } catch (_) {}
    }
    if (mounted) setState(() => _loading = false);
  }

  void _installUnauthorizedHandler() {
    _api.onUnauthorized = () async {
      try {
        await _sessionStorage.delete(key: _sessionTokenKey);
      } catch (_) {}
      final navigator = _appNavigatorKey.currentState;
      if (navigator == null) return;
      _api.onUnauthorized = null;
      navigator.pushAndRemoveUntil(
        MaterialPageRoute<void>(builder: (_) => LoginPage(api: _api)),
        (_) => false,
      );
    };
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (_token != null && _userId != null) {
      return PropertyListPage(api: _api, token: _token!, userId: _userId!);
    }
    return LoginPage(api: _api);
  }
}

class LoginPage extends StatefulWidget {
  const LoginPage({this.api, super.key});

  final ApiClient? api;

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  late final ApiClient _api;
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _api = widget.api ?? ApiClient();
  }

  Future<void> _login() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final token = await _api.login(_email.text.trim(), _password.text);
      final user = await _api.getCurrentUser(token);
      final rawUserId = user['id'];
      if (rawUserId == null || '$rawUserId'.trim().isEmpty) {
        throw const ApiException(
            'A API não retornou o identificador da conta.');
      }
      if (!mounted) return;
      try {
        await _sessionStorage.write(key: _sessionTokenKey, value: token);
      } catch (_) {
        // Keep the current login usable even if secure storage is unavailable.
      }
      if (!mounted) return;
      _api.onUnauthorized = () {
        unawaited(
            _sessionStorage.delete(key: _sessionTokenKey).catchError((_) {}));
        final navigator = _appNavigatorKey.currentState;
        if (navigator == null) return;
        _api.onUnauthorized = null;
        navigator.pushAndRemoveUntil(
          MaterialPageRoute<void>(builder: (_) => LoginPage(api: _api)),
          (_) => false,
        );
      };
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
            builder: (_) => PropertyListPage(
                api: _api, token: token, userId: '$rawUserId')),
      );
    } on ApiException catch (error) {
      setState(() => _error = error.message);
    } catch (_) {
      setState(() => _error =
          'Não foi possível conectar à API. Verifique o endereço e tente novamente.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 460),
              child: ListView(
                padding: const EdgeInsets.all(24),
                shrinkWrap: true,
                children: [
                  Container(
                    width: 76,
                    height: 76,
                    decoration: BoxDecoration(
                        color: _green.withValues(alpha: .1),
                        borderRadius: BorderRadius.circular(24)),
                    child: const Icon(Icons.travel_explore,
                        size: 42, color: _green),
                  ),
                  const SizedBox(height: 24),
                  Text('Radar Leilão',
                      style: Theme.of(context)
                          .textTheme
                          .headlineMedium
                          ?.copyWith(fontWeight: FontWeight.w800, color: _ink)),
                  const SizedBox(height: 8),
                  Text('Encontre oportunidades imobiliárias em um só lugar.',
                      style: Theme.of(context)
                          .textTheme
                          .bodyLarge
                          ?.copyWith(color: Colors.black54)),
                  const SizedBox(height: 32),
                  TextField(
                      controller: _email,
                      keyboardType: TextInputType.emailAddress,
                      autofillHints: const [AutofillHints.username],
                      decoration: const InputDecoration(
                          labelText: 'E-mail',
                          prefixIcon: Icon(Icons.mail_outline))),
                  const SizedBox(height: 14),
                  TextField(
                      controller: _password,
                      obscureText: true,
                      autofillHints: const [AutofillHints.password],
                      onSubmitted: (_) => _login(),
                      decoration: const InputDecoration(
                          labelText: 'Senha',
                          prefixIcon: Icon(Icons.lock_outline))),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    Text(_error!,
                        style: TextStyle(
                            color: Theme.of(context).colorScheme.error)),
                  ],
                  const SizedBox(height: 22),
                  SizedBox(
                      height: 52,
                      child: FilledButton(
                          onPressed: _loading ? null : _login,
                          child: _loading
                              ? const SizedBox(
                                  width: 22,
                                  height: 22,
                                  child:
                                      CircularProgressIndicator(strokeWidth: 2))
                              : const Text('Entrar'))),
                ],
              ),
            ),
          ),
        ),
      );
}

class PropertyListPage extends StatefulWidget {
  const PropertyListPage(
      {required this.api,
      required this.token,
      required this.userId,
      super.key});

  final ApiClient api;
  final String token;
  final String userId;

  @override
  State<PropertyListPage> createState() => _PropertyListPageState();
}

class _PropertyListPageState extends State<PropertyListPage> {
  static const _propertiesPerPage = 10;
  String get _favoritesStorageKey => 'favorite_property_ids_${widget.userId}';
  final _search = TextEditingController();
  Timer? _searchDebounce;
  String _searchTerm = '';
  late Future<List<Map<String, dynamic>>> _properties;
  int _currentPage = 1;
  int _listGeneration = 0;
  bool _hasMoreProperties = true;
  bool _loadingMoreProperties = false;
  String? _loadMoreError;
  Set<String> _favoriteIds = <String>{};
  bool _showFavorites = false;
  String _status = 'ativos';
  String _ordering = 'score';
  String? _state;
  String? _city;
  double? _maxPrice;
  double? _minDiscount;

  @override
  void initState() {
    super.initState();
    _properties = _loadFirstPage(_listGeneration);
    _loadFavorites();
  }

  Future<void> _loadFavorites() async {
    try {
      final preferences = await SharedPreferences.getInstance();
      final ids = preferences.getStringList(_favoritesStorageKey) ?? <String>[];
      if (mounted) setState(() => _favoriteIds = ids.toSet());
    } catch (_) {
      // Favorites remain usable for this session if local storage is unavailable.
    }
  }

  String? _propertyId(Map<String, dynamic> property) {
    final id = property['id'];
    if (id == null || '$id'.trim().isEmpty) return null;
    return '$id';
  }

  bool _isFavorite(Map<String, dynamic> property) {
    final id = _propertyId(property);
    return id != null && _favoriteIds.contains(id);
  }

  Future<void> _toggleFavorite(Map<String, dynamic> property) async {
    final id = _propertyId(property);
    if (id == null) return;
    final updated = Set<String>.from(_favoriteIds);
    if (!updated.add(id)) updated.remove(id);
    setState(() => _favoriteIds = updated);
    try {
      final preferences = await SharedPreferences.getInstance();
      await preferences.setStringList(
          _favoritesStorageKey, updated.toList()..sort());
    } catch (_) {
      // Keep the in-memory change even if saving fails.
    }
  }

  Future<List<Map<String, dynamic>>> _load({int page = 1}) =>
      widget.api.getProperties(
        widget.token,
        pagina: page,
        busca: _searchTerm,
        statusLeilao: _status,
        ordenar: _ordering,
        cidade: _city,
        estado: _state,
        valorMaximo: _maxPrice,
        descontoMinimo: _minDiscount,
      );

  Future<void> _refresh() async {
    _listGeneration++;
    final generation = _listGeneration;
    final request = _loadFirstPage(generation);
    setState(() {
      _currentPage = 1;
      _hasMoreProperties = true;
      _loadingMoreProperties = false;
      _loadMoreError = null;
      _properties = request;
    });
    await request;
  }

  Future<List<Map<String, dynamic>>> _loadFirstPage(int generation) async {
    final items = await _load(page: 1);
    if (mounted && generation == _listGeneration) {
      setState(() => _hasMoreProperties = items.length == _propertiesPerPage);
    }
    return items;
  }

  Future<void> _loadMore(List<Map<String, dynamic>> currentItems) async {
    if (_loadingMoreProperties || !_hasMoreProperties) return;
    setState(() {
      _loadingMoreProperties = true;
      _loadMoreError = null;
    });
    final nextPage = _currentPage + 1;
    final generation = _listGeneration;
    try {
      final nextItems = await _load(page: nextPage);
      if (!mounted || generation != _listGeneration) return;
      setState(() {
        _currentPage = nextPage;
        _hasMoreProperties = nextItems.length == _propertiesPerPage;
        _properties = Future.value([...currentItems, ...nextItems]);
      });
    } catch (_) {
      if (!mounted || generation != _listGeneration) return;
      setState(() => _loadMoreError =
          'Não foi possível carregar mais imóveis. Tente novamente.');
    } finally {
      if (mounted && generation == _listGeneration) {
        setState(() => _loadingMoreProperties = false);
      }
    }
  }

  void _resetList() {
    _listGeneration++;
    _currentPage = 1;
    _hasMoreProperties = true;
    _loadingMoreProperties = false;
    _loadMoreError = null;
    _properties = _loadFirstPage(_listGeneration);
  }

  String _money(dynamic value) {
    final amount = value is num ? value : num.tryParse('$value');
    if (amount == null) return 'Valor não informado';
    final rounded = amount.round().toString();
    final grouped =
        rounded.replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (_) => '.');
    return 'R\$ $grouped';
  }

  String _discount(Map<String, dynamic> property) {
    final valuationValue = property['valor_avaliacao'];
    final auctionValue = property['valor_leilao'];
    final valuation = valuationValue is num
        ? valuationValue.toDouble()
        : double.tryParse('$valuationValue');
    final auction = auctionValue is num
        ? auctionValue.toDouble()
        : double.tryParse('$auctionValue');
    final storedValue = property['desconto'];
    final discount = valuation != null && auction != null && valuation > 0
        ? (valuation - auction) / valuation * 100
        : storedValue is num
            ? storedValue.toDouble()
            : double.tryParse('$storedValue');
    if (discount == null) return '';
    return '${discount.toStringAsFixed(0)}% abaixo da avaliação';
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(
          child: RefreshIndicator(
            onRefresh: _refresh,
            child: FutureBuilder<List<Map<String, dynamic>>>(
              future: _properties,
              builder: (context, snapshot) {
                final all = snapshot.data ?? const <Map<String, dynamic>>[];
                final visible =
                    _showFavorites ? all.where(_isFavorite).toList() : all;
                final properties = visible;
                return CustomScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  slivers: [
                    SliverPadding(
                      padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
                      sliver: SliverToBoxAdapter(child: _header(context)),
                    ),
                    SliverPadding(
                      padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
                      sliver: SliverToBoxAdapter(
                          child: _intro(context, all.length)),
                    ),
                    SliverPadding(
                      padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
                      sliver:
                          SliverToBoxAdapter(child: _searchAndFilters(context)),
                    ),
                    if (snapshot.connectionState == ConnectionState.waiting)
                      const SliverFillRemaining(
                          hasScrollBody: false,
                          child: Center(child: CircularProgressIndicator()))
                    else if (snapshot.hasError)
                      SliverFillRemaining(
                          hasScrollBody: false,
                          child: _message(
                              context,
                              Icons.wifi_off_rounded,
                              'Não foi possível carregar os imóveis',
                              'Confira sua conexão e tente novamente.',
                              action: 'Tentar novamente',
                              onAction: _refresh))
                    else if (all.isEmpty)
                      SliverFillRemaining(
                          hasScrollBody: false,
                          child: _message(
                              context,
                              Icons.home_work_outlined,
                              'Nenhum imóvel encontrado',
                              'Altere os filtros ou atualize a lista.'))
                    else if (properties.isEmpty)
                      SliverFillRemaining(
                          hasScrollBody: false,
                          child: _message(
                              context,
                              _showFavorites
                                  ? Icons.favorite_border_rounded
                                  : Icons.search_off_rounded,
                              _showFavorites
                                  ? 'Nenhum favorito disponível'
                                  : 'Nada por aqui',
                              _showFavorites
                                  ? 'Marque imóveis com o coração para encontrá-los aqui.'
                                  : 'Tente outro termo de busca.',
                              action: !_showFavorites && _hasMoreProperties
                                  ? 'Buscar nos próximos imóveis'
                                  : null,
                              onAction: !_showFavorites && _hasMoreProperties
                                  ? () => _loadMore(all)
                                  : null))
                    else ...[
                      SliverPadding(
                        padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
                        sliver: SliverToBoxAdapter(
                            child: Row(children: [
                          Text(_showFavorites ? 'Favoritos' : 'Oportunidades',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleLarge
                                  ?.copyWith(
                                      fontWeight: FontWeight.w800,
                                      color: _ink)),
                          const Spacer(),
                          Text('${properties.length} imóveis',
                              style: Theme.of(context)
                                  .textTheme
                                  .labelLarge
                                  ?.copyWith(color: Colors.black54))
                        ])),
                      ),
                      SliverPadding(
                        padding: const EdgeInsets.fromLTRB(20, 4, 20, 28),
                        sliver: SliverList.separated(
                          itemCount: properties.length,
                          separatorBuilder: (_, __) =>
                              const SizedBox(height: 14),
                          itemBuilder: (context, index) => _PropertyCard(
                              property: properties[index],
                              money: _money,
                              discount: _discount,
                              isFavorite: _isFavorite(properties[index]),
                              onFavorite: () =>
                                  _toggleFavorite(properties[index]),
                              onTap: () => Navigator.of(context).push(
                                    MaterialPageRoute<void>(
                                      builder: (_) => PropertyDetailPage(
                                        api: widget.api,
                                        token: widget.token,
                                        property: properties[index],
                                        isFavorite:
                                            _isFavorite(properties[index]),
                                        onFavorite: () =>
                                            _toggleFavorite(properties[index]),
                                      ),
                                    ),
                                  )),
                        ),
                      ),
                      if (!_showFavorites &&
                          (_hasMoreProperties || _loadingMoreProperties))
                        SliverToBoxAdapter(
                          child: Padding(
                            padding: const EdgeInsets.fromLTRB(20, 0, 20, 28),
                            child: Column(children: [
                              if (_loadMoreError != null)
                                Padding(
                                  padding: const EdgeInsets.only(bottom: 8),
                                  child: Text(_loadMoreError!,
                                      textAlign: TextAlign.center,
                                      style: TextStyle(
                                          color: Theme.of(context)
                                              .colorScheme
                                              .error)),
                                ),
                              OutlinedButton.icon(
                                key: const ValueKey('load-more-properties'),
                                onPressed: _loadingMoreProperties
                                    ? null
                                    : () => _loadMore(all),
                                icon: _loadingMoreProperties
                                    ? const SizedBox(
                                        width: 18,
                                        height: 18,
                                        child: CircularProgressIndicator(
                                            strokeWidth: 2))
                                    : const Icon(Icons.expand_more_rounded),
                                label: Text(_loadingMoreProperties
                                    ? 'Carregando imóveis...'
                                    : 'Carregar mais imóveis'),
                              ),
                            ]),
                          ),
                        ),
                    ],
                  ],
                );
              },
            ),
          ),
        ),
      );

  Widget _header(BuildContext context) => Row(
        children: [
          Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                  color: _green, borderRadius: BorderRadius.circular(14)),
              child: const Icon(Icons.travel_explore, color: Colors.white)),
          const SizedBox(width: 11),
          Text('Radar Leilão',
              style: Theme.of(context)
                  .textTheme
                  .titleMedium
                  ?.copyWith(fontWeight: FontWeight.w800, color: _ink)),
          const Spacer(),
          IconButton(
              key: const ValueKey('logout'),
              tooltip: 'Sair da conta',
              onPressed: () {
                widget.api.onUnauthorized = null;
                unawaited(_sessionStorage
                    .delete(key: _sessionTokenKey)
                    .catchError((_) {}));
                _appNavigatorKey.currentState?.pushAndRemoveUntil(
                  MaterialPageRoute<void>(
                      builder: (_) => LoginPage(api: widget.api)),
                  (_) => false,
                );
              },
              icon: const Icon(Icons.logout_rounded)),
          IconButton.filledTonal(
              key: const ValueKey('alerts-open'),
              onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => AlertCenterPage(
                        api: widget.api,
                        token: widget.token,
                      ),
                    ),
                  ),
              tooltip: 'Alertas e notificações',
              icon: const Icon(Icons.notifications_active_outlined)),
          IconButton.filledTonal(
              onPressed: _refresh,
              tooltip: 'Atualizar imóveis',
              icon: const Icon(Icons.refresh_rounded)),
        ],
      );

  Widget _intro(BuildContext context, int count) => Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
            gradient: const LinearGradient(
                colors: [_green, Color(0xFF184D43)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight),
            borderRadius: BorderRadius.circular(24)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Sua próxima oportunidade\npode estar aqui.',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                  height: 1.12)),
          const SizedBox(height: 12),
          Row(children: [
            const Icon(Icons.verified_outlined,
                color: Color(0xFFBCE7D8), size: 18),
            const SizedBox(width: 7),
            Text(
                count > 0
                    ? '$count imóveis disponíveis para explorar'
                    : 'Oportunidades atualizadas pela API',
                style: const TextStyle(color: Color(0xFFE0F2EB)))
          ]),
        ]),
      );

  Widget _searchAndFilters(BuildContext context) => Column(children: [
        TextField(
            controller: _search,
            onChanged: (value) {
              _searchDebounce?.cancel();
              _searchDebounce = Timer(const Duration(milliseconds: 350), () {
                if (!mounted) return;
                setState(() {
                  _searchTerm = value.trim();
                  _resetList();
                });
              });
            },
            decoration: const InputDecoration(
                hintText: 'Buscar por cidade, tipo ou imóvel',
                prefixIcon: Icon(Icons.search_rounded))),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(
              child: DropdownButtonFormField<String>(
                  isExpanded: true,
                  initialValue: _status,
                  decoration: const InputDecoration(
                      labelText: 'Leilões',
                      prefixIcon: Icon(Icons.event_available_outlined),
                      contentPadding:
                          EdgeInsets.symmetric(horizontal: 12, vertical: 8)),
                  items: const [
                    DropdownMenuItem(value: 'ativos', child: Text('Ativos')),
                    DropdownMenuItem(value: 'todos', child: Text('Todos')),
                    DropdownMenuItem(
                        value: 'encerrados', child: Text('Encerrados')),
                    DropdownMenuItem(value: 'sem_data', child: Text('Sem data'))
                  ],
                  onChanged: (value) {
                    if (value == null) return;
                    setState(() {
                      _status = value;
                      _resetList();
                    });
                  })),
          const SizedBox(width: 10),
          Expanded(
              child: DropdownButtonFormField<String>(
                  isExpanded: true,
                  initialValue: _ordering,
                  decoration: const InputDecoration(
                      labelText: 'Ordenar',
                      prefixIcon: Icon(Icons.swap_vert_rounded),
                      contentPadding:
                          EdgeInsets.symmetric(horizontal: 12, vertical: 8)),
                  items: const [
                    DropdownMenuItem(value: 'score', child: Text('Destaques')),
                    DropdownMenuItem(
                        value: 'preco', child: Text('Menor preço')),
                    DropdownMenuItem(
                        value: 'desconto', child: Text('Desconto')),
                    DropdownMenuItem(value: 'area', child: Text('Área'))
                  ],
                  onChanged: (value) {
                    if (value == null) return;
                    setState(() {
                      _ordering = value;
                      _resetList();
                    });
                  })),
        ]),
        const SizedBox(height: 10),
        Row(children: [
          OutlinedButton.icon(
              onPressed: () => _showMoreFilters(context),
              icon: const Icon(Icons.tune_rounded, size: 18),
              label: Text(_activeFilterCount == 0
                  ? 'Mais filtros'
                  : 'Filtros ($_activeFilterCount)')),
          const Spacer(),
          OutlinedButton.icon(
            key: const ValueKey('favorites-toggle'),
            onPressed: () => setState(() => _showFavorites = !_showFavorites),
            icon: Icon(_showFavorites
                ? Icons.home_work_outlined
                : Icons.favorite_border_rounded),
            label: Text(_showFavorites ? 'Oportunidades' : 'Favoritos'),
          ),
        ]),
      ]);

  int get _activeFilterCount => [_state, _city, _maxPrice, _minDiscount]
      .where((value) => value != null)
      .length;

  Future<void> _showMoreFilters(BuildContext context) async {
    final filters = await showModalBottomSheet<_PropertyFilters>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _MoreFiltersSheet(
        city: _city,
        state: _state,
        maxPrice: _maxPrice,
        minDiscount: _minDiscount,
      ),
    );
    if (filters != null && mounted) {
      setState(() {
        _city = filters.city;
        _state = filters.state;
        _maxPrice = filters.maxPrice;
        _minDiscount = filters.minDiscount;
        _resetList();
      });
    }
  }

  Widget _message(
          BuildContext context, IconData icon, String title, String subtitle,
          {String? action, VoidCallback? onAction}) =>
      Center(
        child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Icon(icon, size: 44, color: _green.withValues(alpha: .7)),
              const SizedBox(height: 14),
              Text(title,
                  textAlign: TextAlign.center,
                  style: Theme.of(context)
                      .textTheme
                      .titleMedium
                      ?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              Text(subtitle,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.black54)),
              if (action != null) ...[
                const SizedBox(height: 14),
                TextButton(onPressed: onAction, child: Text(action))
              ]
            ])),
      );
}

class _PropertyFilters {
  const _PropertyFilters({
    required this.city,
    required this.state,
    required this.maxPrice,
    required this.minDiscount,
  });

  final String? city;
  final String? state;
  final double? maxPrice;
  final double? minDiscount;
}

class _MoreFiltersSheet extends StatefulWidget {
  const _MoreFiltersSheet({
    required this.city,
    required this.state,
    required this.maxPrice,
    required this.minDiscount,
  });

  final String? city;
  final String? state;
  final double? maxPrice;
  final double? minDiscount;

  @override
  State<_MoreFiltersSheet> createState() => _MoreFiltersSheetState();
}

class _MoreFiltersSheetState extends State<_MoreFiltersSheet> {
  late final _city = TextEditingController(text: widget.city ?? '');
  late final _state = TextEditingController(text: widget.state ?? '');
  late final _price =
      TextEditingController(text: widget.maxPrice?.toStringAsFixed(0) ?? '');
  late final _discount =
      TextEditingController(text: widget.minDiscount?.toStringAsFixed(0) ?? '');
  String? _error;

  @override
  void dispose() {
    _city.dispose();
    _state.dispose();
    _price.dispose();
    _discount.dispose();
    super.dispose();
  }

  void _apply() {
    final state = _state.text.trim().toUpperCase();
    if (state.isNotEmpty && !RegExp(r'^[A-Z]{2}$').hasMatch(state)) {
      setState(() => _error = 'Informe a sigla do estado com 2 letras.');
      return;
    }
    final maxPrice = _parseNumber(_price.text);
    if (_price.text.trim().isNotEmpty && (maxPrice == null || maxPrice <= 0)) {
      setState(() => _error = 'Informe um preço máximo válido.');
      return;
    }
    final minDiscount = _parseNumber(_discount.text);
    if (_discount.text.trim().isNotEmpty &&
        (minDiscount == null || minDiscount < 0 || minDiscount > 100)) {
      setState(() => _error = 'O desconto deve ficar entre 0% e 100%.');
      return;
    }
    Navigator.pop(
      context,
      _PropertyFilters(
        city: _city.text.trim().isEmpty ? null : _city.text.trim(),
        state: state.isEmpty ? null : state,
        maxPrice: maxPrice,
        minDiscount: minDiscount,
      ),
    );
  }

  double? _parseNumber(String value) {
    var normalized = value.trim().replaceAll(' ', '').replaceAll('R\$', '');
    if (normalized.contains(',')) {
      normalized = normalized.replaceAll('.', '').replaceAll(',', '.');
    }
    return double.tryParse(normalized);
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.fromLTRB(
            20, 4, 20, MediaQuery.viewInsetsOf(context).bottom + 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Refinar busca',
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: 16),
            TextField(
                controller: _city,
                decoration: const InputDecoration(
                    labelText: 'Cidade',
                    prefixIcon: Icon(Icons.location_city_outlined))),
            const SizedBox(height: 10),
            TextField(
                controller: _state,
                textCapitalization: TextCapitalization.characters,
                maxLength: 2,
                decoration: const InputDecoration(
                    labelText: 'Estado (UF)',
                    prefixIcon: Icon(Icons.map_outlined))),
            const SizedBox(height: 10),
            Row(children: [
              Expanded(
                  child: TextField(
                      controller: _price,
                      keyboardType:
                          const TextInputType.numberWithOptions(decimal: true),
                      onChanged: (_) => setState(() => _error = null),
                      decoration: const InputDecoration(
                          labelText: 'Preço máximo', prefixText: 'R\$ '))),
              const SizedBox(width: 10),
              Expanded(
                  child: TextField(
                      controller: _discount,
                      keyboardType:
                          const TextInputType.numberWithOptions(decimal: true),
                      onChanged: (_) => setState(() => _error = null),
                      decoration: const InputDecoration(
                          labelText: 'Desconto mínimo', suffixText: '%')))
            ]),
            const SizedBox(height: 16),
            if (_error != null) ...[
              Text(_error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error)),
              const SizedBox(height: 10),
            ],
            Row(children: [
              TextButton(
                  onPressed: () {
                    _city.clear();
                    _state.clear();
                    _price.clear();
                    _discount.clear();
                  },
                  child: const Text('Limpar')),
              const Spacer(),
              FilledButton(
                  onPressed: _apply, child: const Text('Aplicar filtros'))
            ]),
          ],
        ),
      );
}

class _PropertyCard extends StatelessWidget {
  const _PropertyCard(
      {required this.property,
      required this.money,
      required this.discount,
      required this.isFavorite,
      required this.onFavorite,
      required this.onTap});

  final Map<String, dynamic> property;
  final String Function(dynamic) money;
  final String Function(Map<String, dynamic>) discount;
  final bool isFavorite;
  final VoidCallback onFavorite;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final title = '${property['titulo'] ?? 'Imóvel'}';
    final place = [property['cidade'], property['estado']]
        .where((part) => part != null && '$part'.trim().isNotEmpty)
        .join(' · ');
    final photo = property['imagem'] ??
        (property['imagens'] is List && (property['imagens'] as List).isNotEmpty
            ? (property['imagens'] as List).first
            : null);
    final area = property['area'];
    final kind = property['tipo'];
    final savings = discount(property);
    return InkWell(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(22),
            border: Border.all(color: const Color(0xFFE9EEEA)),
            boxShadow: const [
              BoxShadow(
                  color: Color(0x080A3028),
                  blurRadius: 16,
                  offset: Offset(0, 5))
            ]),
        clipBehavior: Clip.antiAlias,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(
              height: 174,
              width: double.infinity,
              child: Stack(fit: StackFit.expand, children: [
                photo is String && photo.isNotEmpty
                    ? Image.network(photo,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => _photoPlaceholder())
                    : _photoPlaceholder(),
                Positioned(
                  top: 8,
                  right: 8,
                  child: Material(
                    color: Colors.white.withValues(alpha: .94),
                    shape: const CircleBorder(),
                    child: IconButton(
                      key: ValueKey('favorite-${property['id']}'),
                      tooltip: isFavorite
                          ? 'Remover dos favoritos'
                          : 'Adicionar aos favoritos',
                      onPressed: onFavorite,
                      icon: Icon(isFavorite
                          ? Icons.favorite_rounded
                          : Icons.favorite_border_rounded),
                      color: _green,
                    ),
                  ),
                ),
              ])),
          Padding(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      if (kind is String && kind.isNotEmpty) _tag(kind),
                      const Spacer(),
                      if (savings.isNotEmpty) _tag(savings, highlight: true)
                    ]),
                    const SizedBox(height: 10),
                    Text(title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context)
                            .textTheme
                            .titleMedium
                            ?.copyWith(
                                fontWeight: FontWeight.w800, color: _ink)),
                    if (place.isNotEmpty) ...[
                      const SizedBox(height: 5),
                      Row(children: [
                        const Icon(Icons.place_outlined,
                            size: 16, color: Colors.black45),
                        const SizedBox(width: 3),
                        Expanded(
                            child: Text(place,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(color: Colors.black54)))
                      ])
                    ],
                    const SizedBox(height: 14),
                    Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                      Expanded(
                          child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                            const Text('Lance atual',
                                style: TextStyle(
                                    fontSize: 12, color: Colors.black54)),
                            const SizedBox(height: 2),
                            Text(money(property['valor_leilao']),
                                style: Theme.of(context)
                                    .textTheme
                                    .titleLarge
                                    ?.copyWith(
                                        fontWeight: FontWeight.w800,
                                        color: _green))
                          ])),
                      if (area != null)
                        _detail(Icons.square_foot_rounded, '$area m²'),
                      if (property['quartos'] != null) ...[
                        const SizedBox(width: 10),
                        _detail(Icons.bed_outlined, '${property['quartos']}')
                      ]
                    ]),
                  ])),
        ]),
      ),
    );
  }

  Widget _photoPlaceholder() => Container(
      color: const Color(0xFFE4EEE8),
      child: const Center(
          child: Icon(Icons.home_work_outlined, size: 48, color: _green)));

  Widget _tag(String label, {bool highlight = false}) => Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
          color: highlight ? const Color(0xFFE5F4ED) : const Color(0xFFF1F4F1),
          borderRadius: BorderRadius.circular(20)),
      child: Text(label,
          style: TextStyle(
              color: highlight ? _green : const Color(0xFF4E625A),
              fontSize: 11,
              fontWeight: FontWeight.w700)));

  Widget _detail(IconData icon, String label) => Row(children: [
        Icon(icon, size: 16, color: Colors.black45),
        const SizedBox(width: 3),
        Text(label, style: const TextStyle(fontSize: 12, color: Colors.black54))
      ]);
}

class PropertyDetailPage extends StatefulWidget {
  const PropertyDetailPage({
    required this.api,
    required this.token,
    required this.property,
    required this.isFavorite,
    required this.onFavorite,
    super.key,
  });

  final ApiClient api;
  final String token;
  final Map<String, dynamic> property;
  final bool isFavorite;
  final VoidCallback onFavorite;

  @override
  State<PropertyDetailPage> createState() => _PropertyDetailPageState();
}

class _PropertyDetailPageState extends State<PropertyDetailPage> {
  late Future<Map<String, dynamic>> _property;
  int _photoIndex = 0;
  late bool _isFavorite = widget.isFavorite;

  void _toggleFavorite() {
    setState(() => _isFavorite = !_isFavorite);
    widget.onFavorite();
  }

  @override
  void initState() {
    super.initState();
    _property = _load();
  }

  Future<Map<String, dynamic>> _load() {
    final id = widget.property['id'];
    return id == null
        ? Future.value(widget.property)
        : widget.api.getProperty(widget.token, id);
  }

  String _money(dynamic value) {
    final number = value is num ? value.toDouble() : double.tryParse('$value');
    if (number == null) return 'Não informado';
    final digits = number.toStringAsFixed(2).split('.');
    final whole =
        digits[0].replaceAllMapped(RegExp(r'(?<=\d)(?=(\d{3})+$)'), (_) => '.');
    return 'R\$ $whole,${digits[1]}';
  }

  String _discount(Map<String, dynamic> property) {
    final valuation = property['valor_avaliacao'];
    final auction = property['valor_leilao'];
    if (valuation is! num || auction is! num || valuation <= 0) {
      final stored = property['desconto'];
      return stored is num ? '${stored.toStringAsFixed(0)}%' : 'Não informado';
    }
    return '${((valuation - auction) / valuation * 100).toStringAsFixed(0)}%';
  }

  Future<void> _openLink(dynamic rawUrl, String label) async {
    final uri = rawUrl is String ? Uri.tryParse(rawUrl.trim()) : null;
    if (uri == null ||
        !const {'http', 'https'}.contains(uri.scheme.toLowerCase()) ||
        uri.host.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('$label indisponível para este imóvel.')),
      );
      return;
    }
    try {
      final opened = await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (!opened && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Não foi possível abrir $label.')),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Não foi possível abrir $label.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('Detalhes do imóvel'),
          actions: [
            IconButton(
              key: const ValueKey('detail-favorite'),
              tooltip: _isFavorite
                  ? 'Remover dos favoritos'
                  : 'Adicionar aos favoritos',
              onPressed: _toggleFavorite,
              icon: Icon(_isFavorite
                  ? Icons.favorite_rounded
                  : Icons.favorite_border_rounded),
              color: _green,
            ),
          ],
        ),
        body: FutureBuilder<Map<String, dynamic>>(
          future: _property,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError || !snapshot.hasData) {
              return Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    const Text('Não foi possível carregar os detalhes.'),
                    const SizedBox(height: 12),
                    OutlinedButton(
                      onPressed: () => setState(() => _property = _load()),
                      child: const Text('Tentar novamente'),
                    ),
                  ]),
                ),
              );
            }
            return _content(context, snapshot.data!);
          },
        ),
      );

  Widget _content(BuildContext context, Map<String, dynamic> property) {
    final images = <String>[];
    final rawImages = property['imagens'];
    if (rawImages is List) {
      images
          .addAll(rawImages.whereType<String>().where((url) => url.isNotEmpty));
    }
    final mainImage = property['imagem'];
    if (images.isEmpty && mainImage is String && mainImage.isNotEmpty) {
      images.add(mainImage);
    }
    final place = [property['endereco'], property['cidade'], property['estado']]
        .where((part) => part != null && '$part'.trim().isNotEmpty)
        .join(', ');

    return ListView(
      padding: const EdgeInsets.only(bottom: 28),
      children: [
        SizedBox(
          height: 260,
          child: images.isEmpty
              ? const _DetailPhotoPlaceholder()
              : PageView.builder(
                  itemCount: images.length,
                  onPageChanged: (index) => setState(() => _photoIndex = index),
                  itemBuilder: (context, index) => Image.network(
                    images[index],
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) =>
                        const _DetailPhotoPlaceholder(),
                  ),
                ),
        ),
        if (images.length > 1)
          Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Column(children: [
              Text('${_photoIndex + 1} / ${images.length}',
                  key: const ValueKey('gallery-position'),
                  style: const TextStyle(color: Colors.black54, fontSize: 12)),
              const SizedBox(height: 6),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(
                  images.length,
                  (index) => Container(
                    width: 7,
                    height: 7,
                    margin: const EdgeInsets.symmetric(horizontal: 3),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: index == _photoIndex ? _green : Colors.black26,
                    ),
                  ),
                ),
              ),
            ]),
          ),
        Padding(
          padding: const EdgeInsets.all(20),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${property['titulo'] ?? 'Imóvel'}',
                style: Theme.of(context)
                    .textTheme
                    .headlineSmall
                    ?.copyWith(color: _ink, fontWeight: FontWeight.w800)),
            if (place.isNotEmpty) ...[
              const SizedBox(height: 8),
              Row(children: [
                const Icon(Icons.place_outlined, color: _green, size: 19),
                const SizedBox(width: 5),
                Expanded(child: Text(place)),
              ]),
            ],
            const SizedBox(height: 20),
            _DetailSection(title: 'Valores', children: [
              _DetailRow('Lance do leilão', _money(property['valor_leilao'])),
              _DetailRow(
                  'Valor de avaliação', _money(property['valor_avaliacao'])),
              _DetailRow('Desconto', _discount(property)),
            ]),
            const SizedBox(height: 16),
            _DetailSection(title: 'Leilão', children: [
              _DetailRow('1º leilão', property['data_primeiro_leilao']),
              _DetailRow('2º leilão', property['data_segundo_leilao']),
              _DetailRow('Licitação aberta', property['data_licitacao_aberta']),
              _DetailRow('Modalidade', property['modalidade']),
              _DetailRow('Leiloeiro', property['leiloeiro']),
              _DetailRow('Processo', property['processo']),
              _DetailRow('Fonte', property['fonte']),
            ]),
            const SizedBox(height: 16),
            _DetailSection(title: 'Características', children: [
              _DetailRow('Tipo', property['tipo']),
              _DetailRow('Área',
                  property['area'] == null ? null : '${property['area']} m²'),
              _DetailRow('Quartos', property['quartos']),
              _DetailRow('Banheiros', property['banheiros']),
              _DetailRow('Vagas', property['vagas']),
            ]),
            const SizedBox(height: 16),
            _DetailSection(title: 'Condições informadas', children: [
              _DetailRow('Ocupação', _occupancy(property['ocupado'])),
              _DetailRow('Aceita FGTS', _yesNo(property['aceita_fgts'])),
              _DetailRow('Aceita financiamento',
                  _yesNo(property['aceita_financiamento'])),
            ]),
            if (_hasLink(property['url']) ||
                _hasLink(property['link_edital'])) ...[
              const SizedBox(height: 16),
              _DetailSection(title: 'Links do anúncio', children: [
                if (_hasLink(property['url']))
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                      onPressed: () => _openLink(property['url'], 'anúncio'),
                      icon: const Icon(Icons.open_in_new),
                      label: const Text('Abrir anúncio original'),
                    ),
                  ),
                if (_hasLink(property['link_edital']))
                  SizedBox(
                    width: double.infinity,
                    child: OutlinedButton.icon(
                      onPressed: () =>
                          _openLink(property['link_edital'], 'edital'),
                      icon: const Icon(Icons.description_outlined),
                      label: const Text('Abrir edital'),
                    ),
                  ),
              ]),
            ],
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                key: const ValueKey('profitability-open'),
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => ProfitabilitySimulatorPage(
                      api: widget.api,
                      token: widget.token,
                      property: property,
                    ),
                  ),
                ),
                icon: const Icon(Icons.calculate_outlined),
                label: const Text('Simular rentabilidade'),
              ),
            ),
          ]),
        ),
      ],
    );
  }

  bool _hasLink(dynamic value) => value is String && value.trim().isNotEmpty;

  String _yesNo(dynamic value) {
    if (value == null || '$value'.trim().isEmpty) return 'Não informado';
    if (value is bool) return value ? 'Sim' : 'Não';
    final normalized = '$value'.trim().toLowerCase();
    if ({'sim', 's', '1', 'true', 'yes'}.contains(normalized)) return 'Sim';
    if ({'não', 'nao', 'n', '0', 'false', 'no'}.contains(normalized)) {
      return 'Não';
    }
    return '$value';
  }

  String _occupancy(dynamic value) {
    if (value == null || '$value'.trim().isEmpty) return 'Não informado';
    if (value is bool) return value ? 'Ocupado' : 'Desocupado';
    return '$value';
  }
}

class _DetailSection extends StatelessWidget {
  const _DetailSection({required this.title, required this.children});
  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: const Color(0xFFE9EEEA)),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title,
              style: const TextStyle(
                  color: _ink, fontWeight: FontWeight.w800, fontSize: 16)),
          const SizedBox(height: 8),
          ...children,
        ]),
      );
}

class _DetailRow extends StatelessWidget {
  _DetailRow(this.label, dynamic value)
      : value = value == null || '$value'.trim().isEmpty
            ? 'Não informado'
            : '$value';
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 5),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(
              child:
                  Text(label, style: const TextStyle(color: Colors.black54))),
          const SizedBox(width: 12),
          Flexible(
            child: Text(value,
                textAlign: TextAlign.end,
                style:
                    const TextStyle(color: _ink, fontWeight: FontWeight.w600)),
          ),
        ]),
      );
}

class _DetailPhotoPlaceholder extends StatelessWidget {
  const _DetailPhotoPlaceholder();
  @override
  Widget build(BuildContext context) => Container(
        color: const Color(0xFFE4EEE8),
        child: const Center(
            child: Icon(Icons.home_work_outlined, size: 60, color: _green)),
      );
}
