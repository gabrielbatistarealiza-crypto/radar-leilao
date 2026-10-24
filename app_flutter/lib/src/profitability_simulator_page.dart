import 'package:flutter/material.dart';

import 'api_client.dart';

class ProfitabilitySimulatorPage extends StatefulWidget {
  const ProfitabilitySimulatorPage({
    required this.api,
    required this.token,
    required this.property,
    super.key,
  });

  final ApiClient api;
  final String token;
  final Map<String, dynamic> property;

  @override
  State<ProfitabilitySimulatorPage> createState() =>
      _ProfitabilitySimulatorPageState();
}

class _ProfitabilitySimulatorPageState
    extends State<ProfitabilitySimulatorPage> {
  final _name = TextEditingController();
  final _observations = TextEditingController();
  final _controllers = <String, TextEditingController>{
    for (final key in [
      'preco_aquisicao',
      'impostos_taxas',
      'custos_juridicos',
      'reformas',
      'outras_despesas',
      'valor_revenda',
    ])
      key: TextEditingController(),
  };
  List<Map<String, dynamic>> _scenarios = [];
  int? _opportunityId;
  bool _loading = true;
  bool _saving = false;
  String? _error;

  static const _fields = <(String, String, bool)>[
    ('preco_aquisicao', 'Preço de aquisição', true),
    ('impostos_taxas', 'Impostos e taxas', false),
    ('custos_juridicos', 'Custos jurídicos', false),
    ('reformas', 'Reformas', false),
    ('outras_despesas', 'Outras despesas', false),
    ('valor_revenda', 'Revenda esperada', true),
  ];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final propertyId = widget.property['id'];
      if (propertyId is! int) {
        throw const ApiException('Imóvel sem identificador válido.');
      }
      final opportunities =
          await widget.api.getPropertyOpportunities(widget.token, propertyId);
      if (opportunities.isNotEmpty) {
        _opportunityId = opportunities.first['id'] as int;
        _scenarios = await widget.api
            .getProfitabilityScenarios(widget.token, _opportunityId!);
      }
    } catch (error) {
      _error = '$error';
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _save() async {
    if (_name.text.trim().isEmpty) {
      setState(() => _error = 'Informe um nome para o cenário.');
      return;
    }
    final values = <String, dynamic>{};
    for (final (key, label, required) in _fields) {
      final raw = _controllers[key]!.text.trim().replaceAll(',', '.');
      if (raw.isEmpty && required) {
        setState(() => _error = 'Preencha $label.');
        return;
      }
      final value = raw.isEmpty ? null : double.tryParse(raw);
      if (raw.isNotEmpty && (value == null || value < 0)) {
        setState(() => _error = 'Informe um valor válido para $label.');
        return;
      }
      values[key] = value;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      var opportunityId = _opportunityId;
      if (opportunityId == null) {
        final user = await widget.api.getCurrentUser(widget.token);
        final userId = user['id'];
        if (userId is! int) {
          throw const ApiException('Não foi possível identificar a conta.');
        }
        final opportunity = await widget.api.createPropertyOpportunity(
            widget.token, widget.property['id'] as int, userId);
        opportunityId = opportunity['id'] as int;
        _opportunityId = opportunityId;
      }
      final saved = await widget.api
          .saveProfitabilityScenario(widget.token, opportunityId, {
        'nome': _name.text.trim(),
        ...values,
        'observacoes': _observations.text.trim().isEmpty
            ? null
            : _observations.text.trim(),
      });
      setState(() {
        _scenarios.insert(0, saved);
        _name.clear();
        _observations.clear();
        for (final controller in _controllers.values) {
          controller.clear();
        }
      });
    } catch (error) {
      setState(() => _error = '$error');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  String _money(dynamic value) {
    final number = value is num ? value.toDouble() : double.tryParse('$value');
    if (number == null) return '—';
    final digits = number.toStringAsFixed(2).split('.');
    final whole =
        digits[0].replaceAllMapped(RegExp(r'(?<=\d)(?=(\d{3})+$)'), (_) => '.');
    return 'R\$ $whole,${digits[1]}';
  }

  String _percent(dynamic value) => value == null
      ? '—'
      : '${(value is num ? value.toDouble() : double.parse('$value')).toStringAsFixed(2).replaceAll('.', ',')}%';

  @override
  void dispose() {
    _name.dispose();
    _observations.dispose();
    for (final controller in _controllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Simulador de rentabilidade')),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : ListView(padding: const EdgeInsets.all(20), children: [
                Text('${widget.property['titulo'] ?? 'Imóvel'}',
                    style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                const Text(
                    'Estimativas não representam garantia de retorno. Custos vazios entram como zero e ficam destacados.'),
                const SizedBox(height: 8),
                const Text(
                    'Ao salvar seu primeiro cenário, será criada uma oportunidade na sua conta e seu interesse por este imóvel será registrado.'),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!,
                      style: TextStyle(
                          color: Theme.of(context).colorScheme.error)),
                ],
                const SizedBox(height: 18),
                TextField(
                    controller: _name,
                    maxLength: 120,
                    decoration:
                        const InputDecoration(labelText: 'Nome do cenário')),
                for (final (key, label, required) in _fields)
                  Padding(
                    padding: const EdgeInsets.only(top: 10),
                    child: TextField(
                      controller: _controllers[key],
                      keyboardType:
                          const TextInputType.numberWithOptions(decimal: true),
                      decoration: InputDecoration(
                          labelText: required ? label : '$label (opcional)',
                          prefixText: 'R\$ '),
                    ),
                  ),
                const SizedBox(height: 10),
                TextField(
                    controller: _observations,
                    maxLength: 5000,
                    maxLines: 2,
                    decoration: const InputDecoration(
                        labelText: 'Premissas e observações')),
                const SizedBox(height: 12),
                FilledButton(
                    onPressed: _saving ? null : _save,
                    child: Text(_saving ? 'Salvando…' : 'Salvar cenário')),
                const SizedBox(height: 24),
                Text('Cenários salvos',
                    style: Theme.of(context).textTheme.titleLarge),
                if (_scenarios.isEmpty)
                  const Padding(
                      padding: EdgeInsets.only(top: 10),
                      child: Text(
                          'Ainda não há cenários salvos para este imóvel.')),
                for (final scenario in _scenarios) _scenarioCard(scenario),
              ]),
      );

  Widget _scenarioCard(Map<String, dynamic> scenario) {
    final missing =
        (scenario['custos_nao_informados'] as List? ?? const []).join(', ');
    return Card(
      margin: const EdgeInsets.only(top: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${scenario['nome']}',
              style:
                  const TextStyle(fontWeight: FontWeight.bold, fontSize: 17)),
          const SizedBox(height: 10),
          Text('Custo total  ${_money(scenario['custo_total'])}'),
          Text('Lucro estimado  ${_money(scenario['lucro_estimado'])}'),
          Text('Margem sobre revenda  ${_percent(scenario['margem_revenda'])}'),
          Text('ROI  ${_percent(scenario['roi'])}'),
          Text(
              'Aquisição ${_money(scenario['preco_aquisicao'])} · Revenda ${_money(scenario['valor_revenda'])}'),
          if (missing.isNotEmpty)
            Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text(
                    'Custos por confirmar (assumidos como zero na estimativa): $missing. ROI e margem não pontuam no score até confirmar os custos.',
                    style:
                        TextStyle(color: Theme.of(context).colorScheme.error))),
          if ('${scenario['observacoes'] ?? ''}'.isNotEmpty)
            Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text('Premissas: ${scenario['observacoes']}')),
        ]),
      ),
    );
  }
}
