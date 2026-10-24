import 'package:flutter/material.dart';

import 'api_client.dart';

class AlertCenterPage extends StatefulWidget {
  const AlertCenterPage({
    required this.api,
    required this.token,
    super.key,
  });

  final ApiClient api;
  final String token;

  @override
  State<AlertCenterPage> createState() => _AlertCenterPageState();
}

class _AlertCenterPageState extends State<AlertCenterPage> {
  late Future<_AlertData> _data;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _data = _load();
  }

  Future<_AlertData> _load() async {
    final results = await Future.wait([
      widget.api.getAlerts(widget.token),
      widget.api.getNotifications(widget.token),
      widget.api.getAlertScenarios(widget.token),
    ]);
    return _AlertData(results[0], results[1], results[2]);
  }

  Future<void> _refresh() async {
    final data = _load();
    setState(() => _data = data);
    await data;
  }

  Future<void> _edit([Map<String, dynamic>? existing]) async {
    final List<Map<String, dynamic>> scenarios;
    try {
      scenarios = await widget.api.getAlertScenarios(widget.token);
    } catch (error) {
      _showError(error);
      return;
    }
    if (!mounted) return;
    final saved = await showDialog<bool>(
      context: context,
      builder: (_) => _AlertFormDialog(
        api: widget.api,
        token: widget.token,
        scenarios: scenarios,
        existing: existing,
      ),
    );
    if (saved == true) await _refresh();
  }

  Future<void> _delete(Map<String, dynamic> alert) async {
    final id = alert['id'];
    if (id is! int) return;
    setState(() => _saving = true);
    try {
      await widget.api.deleteAlert(widget.token, id);
      await _refresh();
    } catch (error) {
      _showError(error);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _toggleAlert(Map<String, dynamic> alert, bool active) async {
    final id = alert['id'];
    if (id is! int) return;
    setState(() => _saving = true);
    try {
      await widget.api.saveAlert(
        widget.token,
        {
          'nome': alert['nome'],
          'estado': alert['estado'],
          'cidade': alert['cidade'],
          'preco_maximo': alert['preco_maximo'],
          'desconto_minimo': alert['desconto_minimo'],
          'roi_minimo': alert['roi_minimo'],
          'simulacao_id': alert['simulacao_id'],
          'alertar_prazos_dias': alert['alertar_prazos_dias'] ?? 7,
          'ativo': active,
        },
        id: id,
      );
      await _refresh();
    } catch (error) {
      _showError(error);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _markRead(Map<String, dynamic> notification) async {
    final id = notification['id'];
    if (id is! int) return;
    try {
      await widget.api.markNotificationRead(widget.token, id);
      await _refresh();
    } catch (error) {
      _showError(error);
    }
  }

  void _showError(Object error) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(error.toString())),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Alertas e notificações')),
        floatingActionButton: FloatingActionButton.extended(
          onPressed: _saving ? null : _edit,
          icon: const Icon(Icons.add_alert_outlined),
          label: const Text('Novo alerta'),
        ),
        body: FutureBuilder<_AlertData>(
          future: _data,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return _PageMessage(
                title: 'Não foi possível carregar',
                message: snapshot.error.toString(),
                action: _refresh,
              );
            }
            final data = snapshot.data!;
            return RefreshIndicator(
              onRefresh: _refresh,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 92),
                children: [
                  Text('Meus alertas',
                      style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 8),
                  if (data.alerts.isEmpty)
                    const _EmptySection(
                      text: 'Você ainda não criou alertas.',
                      icon: Icons.notifications_none,
                    )
                  else
                    ...data.alerts.map((alert) => _alertCard(alert)),
                  const SizedBox(height: 24),
                  Text('Histórico de notificações',
                      style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 8),
                  if (data.notifications.isEmpty)
                    const _EmptySection(
                      text: 'Suas notificações aparecerão aqui.',
                      icon: Icons.mark_email_read_outlined,
                    )
                  else
                    ...data.notifications
                        .map((notification) => _notificationCard(notification)),
                ],
              ),
            );
          },
        ),
      );

  Widget _alertCard(Map<String, dynamic> alert) => Card(
        child: ListTile(
          title: Row(children: [
            Expanded(child: Text('${alert['nome'] ?? 'Alerta'}')),
            if (alert['ativo'] != true)
              const Chip(
                  label: Text('Pausado'), visualDensity: VisualDensity.compact),
          ]),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(_criteriaSummary(alert)),
          ),
          isThreeLine: true,
          trailing: Row(mainAxisSize: MainAxisSize.min, children: [
            Semantics(
              label: 'Ativar ou pausar alerta',
              child: Switch.adaptive(
                value: alert['ativo'] == true,
                onChanged:
                    _saving ? null : (value) => _toggleAlert(alert, value),
              ),
            ),
            PopupMenuButton<String>(
              enabled: !_saving,
              onSelected: (action) =>
                  action == 'edit' ? _edit(alert) : _delete(alert),
              itemBuilder: (_) => const [
                PopupMenuItem(value: 'edit', child: Text('Editar')),
                PopupMenuItem(value: 'delete', child: Text('Excluir')),
              ],
            ),
          ]),
        ),
      );

  String _criteriaSummary(Map<String, dynamic> alert) {
    final values = <String>[];
    if (alert['estado'] != null) values.add('${alert['estado']}');
    if (alert['cidade'] != null) values.add('${alert['cidade']}');
    if (alert['preco_maximo'] != null) {
      values.add('até R\$ ${alert['preco_maximo']}');
    }
    if (alert['desconto_minimo'] != null) {
      values.add('desconto ≥ ${alert['desconto_minimo']}%');
    }
    if (alert['roi_minimo'] != null) {
      values.add('ROI ≥ ${alert['roi_minimo']}%');
    }
    values.add('avisar até ${alert['alertar_prazos_dias'] ?? 7} dias antes');
    return values.join(' · ');
  }

  Widget _notificationCard(Map<String, dynamic> item) {
    final read = item['lida'] == true;
    return Card(
      color: read ? null : Theme.of(context).colorScheme.primaryContainer,
      child: ListTile(
        leading: Icon(read ? Icons.notifications_none : Icons.notifications),
        title: Text('${item['titulo'] ?? 'Notificação'}'),
        subtitle: Text('${item['mensagem'] ?? ''}'),
        trailing: read
            ? null
            : IconButton(
                tooltip: 'Marcar como lida',
                onPressed: () => _markRead(item),
                icon: const Icon(Icons.mark_email_read_outlined),
              ),
      ),
    );
  }
}

class _AlertFormDialog extends StatefulWidget {
  const _AlertFormDialog({
    required this.api,
    required this.token,
    required this.scenarios,
    this.existing,
  });

  final ApiClient api;
  final String token;
  final List<Map<String, dynamic>> scenarios;
  final Map<String, dynamic>? existing;

  @override
  State<_AlertFormDialog> createState() => _AlertFormDialogState();
}

class _AlertFormDialogState extends State<_AlertFormDialog> {
  late final TextEditingController _name;
  late final TextEditingController _state;
  late final TextEditingController _city;
  late final TextEditingController _maxPrice;
  late final TextEditingController _minDiscount;
  late final TextEditingController _minRoi;
  late final TextEditingController _days;
  int? _scenarioId;
  String? _error;
  bool _saving = false;

  String? _value(String key) => widget.existing?[key]?.toString();

  @override
  void initState() {
    super.initState();
    _name = TextEditingController(text: _value('nome') ?? '');
    _state = TextEditingController(text: _value('estado') ?? '');
    _city = TextEditingController(text: _value('cidade') ?? '');
    _maxPrice = TextEditingController(text: _value('preco_maximo') ?? '');
    _minDiscount = TextEditingController(text: _value('desconto_minimo') ?? '');
    _minRoi = TextEditingController(text: _value('roi_minimo') ?? '');
    _days = TextEditingController(text: _value('alertar_prazos_dias') ?? '7');
    final currentScenario = widget.existing?['simulacao_id'];
    if (currentScenario is int &&
        widget.scenarios.any((item) => item['id'] == currentScenario)) {
      _scenarioId = currentScenario;
    }
  }

  @override
  void dispose() {
    for (final controller in [
      _name,
      _state,
      _city,
      _maxPrice,
      _minDiscount,
      _minRoi,
      _days,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  Map<String, dynamic> _payload() {
    String? text(TextEditingController controller) =>
        controller.text.trim().isEmpty ? null : controller.text.trim();
    double? number(TextEditingController controller) =>
        double.tryParse(controller.text.trim().replaceAll(',', '.'));
    return {
      'nome': _name.text.trim(),
      'estado': text(_state)?.toUpperCase(),
      'cidade': text(_city),
      'preco_maximo': number(_maxPrice),
      'desconto_minimo': number(_minDiscount),
      'roi_minimo': number(_minRoi),
      'simulacao_id': _scenarioId,
      'alertar_prazos_dias': int.tryParse(_days.text.trim()) ?? 7,
      'ativo': widget.existing?['ativo'] != false,
    };
  }

  Future<void> _save() async {
    final payload = _payload();
    if (payload['nome'] == '') {
      setState(() => _error = 'Informe um nome para o alerta.');
      return;
    }
    if (_state.text.trim().isNotEmpty && _state.text.trim().length != 2) {
      setState(() => _error = 'Informe a sigla do estado com 2 letras.');
      return;
    }
    final numberRules = <(TextEditingController, String, double, double?)>[
      (_maxPrice, 'Preço máximo', 0.01, null),
      (_minDiscount, 'Desconto mínimo', 0, 100),
      (_minRoi, 'ROI mínimo', -100, 10000),
    ];
    for (final (controller, label, minimum, maximum) in numberRules) {
      final raw = controller.text.trim();
      if (raw.isEmpty) continue;
      final parsed = double.tryParse(raw.replaceAll(',', '.'));
      if (parsed == null ||
          parsed < minimum ||
          (maximum != null && parsed > maximum)) {
        setState(() => _error = '$label fora do limite permitido.');
        return;
      }
    }
    final days = int.tryParse(_days.text.trim());
    if (days == null || days < 0 || days > 90) {
      setState(() => _error = 'O prazo deve ficar entre 0 e 90 dias.');
      return;
    }
    if (payload['roi_minimo'] != null && _scenarioId == null) {
      setState(() => _error = 'Escolha um cenário guardado para usar ROI.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final rawId = widget.existing?['id'];
      await widget.api
          .saveAlert(widget.token, payload, id: rawId is int ? rawId : null);
      if (mounted) Navigator.of(context).pop(true);
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: Text(widget.existing == null ? 'Novo alerta' : 'Editar alerta'),
        content: SizedBox(
          width: 440,
          child: SingleChildScrollView(
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              _field(_name, 'Nome do alerta'),
              _field(_state, 'Estado (UF)', maxLength: 2),
              _field(_city, 'Cidade'),
              _field(_maxPrice, 'Preço máximo', numeric: true),
              _field(_minDiscount, 'Desconto mínimo (%)', numeric: true),
              DropdownButtonFormField<int?>(
                initialValue: _scenarioId,
                decoration: const InputDecoration(labelText: 'Cenário de ROI'),
                items: [
                  const DropdownMenuItem<int?>(
                      value: null, child: Text('Sem cenário')),
                  ...widget.scenarios.map((scenario) => DropdownMenuItem<int?>(
                        value: scenario['id'] as int?,
                        child: Text('${scenario['nome']}'),
                      )),
                ],
                onChanged: (value) => setState(() => _scenarioId = value),
              ),
              if (widget.scenarios.isEmpty)
                const Align(
                    alignment: Alignment.centerLeft,
                    child: Padding(
                      padding: EdgeInsets.only(top: 4),
                      child: Text('Crie um cenário completo para ativar o ROI.',
                          style: TextStyle(fontSize: 12)),
                    )),
              _field(_minRoi, 'ROI mínimo (%)', numeric: true),
              _field(_days, 'Avisar antes do leilão (dias)', numeric: true),
              if (_error != null)
                Align(
                    alignment: Alignment.centerLeft,
                    child: Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text(_error!,
                          style: TextStyle(
                              color: Theme.of(context).colorScheme.error)),
                    )),
            ]),
          ),
        ),
        actions: [
          TextButton(
              onPressed: _saving ? null : () => Navigator.pop(context, false),
              child: const Text('Cancelar')),
          FilledButton(
              onPressed: _saving ? null : _save,
              child: _saving
                  ? const SizedBox(
                      height: 18,
                      width: 18,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Salvar')),
        ],
      );

  Widget _field(TextEditingController controller, String label,
          {bool numeric = false, int? maxLength}) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: TextField(
          controller: controller,
          keyboardType: numeric
              ? const TextInputType.numberWithOptions(decimal: true)
              : null,
          maxLength: maxLength,
          decoration: InputDecoration(labelText: label, counterText: ''),
        ),
      );
}

class _AlertData {
  const _AlertData(this.alerts, this.notifications, this.scenarios);

  final List<Map<String, dynamic>> alerts;
  final List<Map<String, dynamic>> notifications;
  final List<Map<String, dynamic>> scenarios;
}

class _EmptySection extends StatelessWidget {
  const _EmptySection({required this.text, required this.icon});

  final String text;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(children: [
            Icon(icon, color: Theme.of(context).colorScheme.primary),
            const SizedBox(width: 12),
            Expanded(child: Text(text)),
          ]),
        ),
      );
}

class _PageMessage extends StatelessWidget {
  const _PageMessage(
      {required this.title, required this.message, required this.action});

  final String title;
  final String message;
  final VoidCallback action;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text(title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton(
                onPressed: action, child: const Text('Tentar novamente')),
          ]),
        ),
      );
}
