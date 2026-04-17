import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter/rendering.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:math' as math;
import 'dart:ui' as ui;

// 全局的主题控制器，默认使用系统主题
final ValueNotifier<ThemeMode> themeNotifier = ValueNotifier(ThemeMode.system);

void main() {
  runApp(const NotebookLMApp());
}

class NotebookLMApp extends StatelessWidget {
  const NotebookLMApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<ThemeMode>(
      valueListenable: themeNotifier,
      builder: (_, ThemeMode currentMode, __) {
        return MaterialApp(
          title: 'NotebookLM Clone',
          debugShowCheckedModeBanner: false,
          themeMode: currentMode,
          // 纯正的 Material 3 亮色主题
          theme: ThemeData(
            colorScheme: ColorScheme.fromSeed(
              seedColor: const Color(0xFF0A57D0), // Google Blue
              brightness: Brightness.light,
            ),
            useMaterial3: true,
            fontFamily: 'Microsoft YaHei',
          ),
          // 纯正的 Material 3 暗色主题
          darkTheme: ThemeData(
            colorScheme: ColorScheme.fromSeed(
              seedColor: const Color(0xFFA8C7FA), // Google Blue Light
              brightness: Brightness.dark,
            ),
            useMaterial3: true,
            fontFamily: 'Microsoft YaHei',
          ),
          home: const NotebookHome(),
        );
      },
    );
  }
}

class NotebookHome extends StatefulWidget {
  const NotebookHome({Key? key}) : super(key: key);

  @override
  State<NotebookHome> createState() => _NotebookHomeState();
}

enum CenterViewMode { chat, document, learning, quiz, studioGraph, studioText }

class ChatMessage {
  final String text;
  final bool isUser;
  final List<String> references;
  ChatMessage({required this.text, required this.isUser, this.references = const []});
}

class Notebook {
  final String id;
  String title;
  Notebook({required this.id, required this.title});
}

class _NotebookHomeState extends State<NotebookHome> {
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  final TextEditingController _chatController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<ChatMessage> _messages = [];
  
  bool _isThinking = false;
  bool _isUploading = false;
  bool _isGeneratingStudio = false;
  String? _activeStudioTool;
  CenterViewMode _centerMode = CenterViewMode.chat;
  String _qaMode = 'mix';
  bool _includeReferences = false;

  List<Map<String, dynamic>> _documents = [];
  Map<String, dynamic>? _selectedDocument;
  List<Map<String, dynamic>> _documentKnowledgeNodes = [];
  bool _isLoadingDocuments = false;
  bool _isLoadingDocumentDetail = false;
  int _documentsPage = 1;
  int _documentsTotal = 0;
  bool _documentsHasNext = false;
  bool _documentsHasPrev = false;
  String? _documentsStatusFilter;
  Map<String, int> _statusCounts = {};
  Map<String, dynamic>? _pipelineStatus;

  List<Map<String, dynamic>> _skillNodes = [];
  bool _isLoadingSkillNodes = false;
  String? _learningNodeName;
  String? _learningContent;
  Map<String, dynamic>? _studioGraphPayload;
  String? _studioGraphLabel;
  String? _studioTextTitle;
  String? _studioTextType;
  String? _studioTextTopic;
  String? _studioTextContent;
  final GlobalKey _graphExportKey = GlobalKey();
  bool _isExportingGraph = false;

  bool _isGeneratingQuiz = false;
  bool _isSubmittingQuiz = false;
  int _quizQuestionCount = 5;
  String? _quizNodeId;
  String? _quizNodeName;
  List<Map<String, dynamic>> _quizQuestions = [];
  Map<String, dynamic> _quizAnswers = {};
  Map<String, dynamic>? _quizResult;

  List<Notebook> _notebooks = [];
  Notebook? _currentNotebook;
  bool _isLoadingNotebooks = false;
  bool _isCreatingNotebook = false;

  final String _apiBaseUrl = _resolveApiBaseUrl();

  static String _resolveApiBaseUrl() {
    const defined = String.fromEnvironment('API_BASE_URL');
    if (defined.isNotEmpty) return defined;
    if (kIsWeb) return 'http://localhost:8000';
    if (defaultTargetPlatform == TargetPlatform.android) return 'http://10.0.2.2:8000';
    return 'http://127.0.0.1:8000';
  }

  @override
  void initState() {
    super.initState();
    _loadInitialData();
  }

  @override
  void dispose() {
    _chatController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _loadInitialData() async {
    await Future.wait([
      _fetchDocuments(resetPage: true),
      _refreshSkillNodes(),
      _refreshPipelineStatus(silent: true),
    ]);
  }

  Future<void> _refreshPipelineStatus({bool silent = false}) async {
    try {
      final result = await _apiGet('/api/documents/pipeline-status');
      if (!mounted) return;
      setState(() => _pipelineStatus = result);
    } catch (error) {
      if (!silent) await _showError(error);
    }
  }

  String _stringOf(dynamic value, {String fallback = ''}) {
    if (value == null) return fallback;
    final text = value.toString();
    return text.isEmpty ? fallback : text;
  }

  double _doubleOf(dynamic value, {double fallback = 0}) {
    if (value is num) return value.toDouble();
    return double.tryParse(value?.toString() ?? '') ?? fallback;
  }

  int _intOf(dynamic value, {int fallback = 0}) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    return int.tryParse(value?.toString() ?? '') ?? fallback;
  }

  Future<void> _showError(Object error) async {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(error.toString(), style: TextStyle(color: Theme.of(context).colorScheme.onErrorContainer)),
        backgroundColor: Theme.of(context).colorScheme.errorContainer,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  String _shortFileName(String fullPath) {
    final normalized = fullPath.replaceAll('\\', '/');
    if (!normalized.contains('/')) return normalized;
    return normalized.split('/').last;
  }

  String _statusText(String status) {
    switch (status.toLowerCase()) {
      case 'processed': return '已处理';
      case 'processing': return '处理中';
      case 'pending': return '等待中';
      case 'failed': return '失败';
      case 'preprocessed': return '预处理';
      case 'completed': return '已完成';
      case 'learning': return '学习中';
      case 'available': return '可学习';
      case 'locked': return '未解锁';
      default: return status;
    }
  }

  Color _statusColor(String status, ColorScheme colorScheme) {
    switch (status.toLowerCase()) {
      case 'processed':
      case 'completed': return Colors.green; // 语义颜色
      case 'processing':
      case 'learning': return Colors.orange;
      case 'failed': return colorScheme.error;
      case 'available': return colorScheme.primary;
      case 'locked': return colorScheme.outline;
      default: return colorScheme.onSurfaceVariant;
    }
  }

  IconData _statusIcon(String status) {
    switch (status.toLowerCase()) {
      case 'processed':
      case 'completed': return Icons.check_circle;
      case 'processing':
      case 'learning': return Icons.autorenew;
      case 'failed': return Icons.error;
      case 'pending': return Icons.schedule;
      case 'preprocessed': return Icons.tune;
      case 'available': return Icons.play_circle;
      case 'locked': return Icons.lock;
      default: return Icons.info_outline;
    }
  }

  Future<Map<String, dynamic>> _apiGet(String path, {Map<String, String>? query}) async {
    final uri = Uri.parse('$_apiBaseUrl$path').replace(queryParameters: query);
    final response = await http.get(uri);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('GET $path 失败: ${response.statusCode} ${response.body}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is Map<String, dynamic>) return decoded;
    return {'data': decoded};
  }

  Future<List<dynamic>> _apiGetList(String path, {Map<String, String>? query}) async {
    final uri = Uri.parse('$_apiBaseUrl$path').replace(queryParameters: query);
    final response = await http.get(uri);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('GET $path 失败: ${response.statusCode} ${response.body}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is List) return decoded;
    if (decoded is Map<String, dynamic> && decoded['data'] is List) {
      return decoded['data'] as List;
    }
    return [];
  }

  Future<Map<String, dynamic>> _apiPost(String path, {Object? body}) async {
    final uri = Uri.parse('$_apiBaseUrl$path');
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: body == null ? null : jsonEncode(body),
    );
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('POST $path 失败: ${response.statusCode} ${response.body}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is Map<String, dynamic>) return decoded;
    return {'data': decoded};
  }

  Future<Map<String, dynamic>> _apiDelete(String path) async {
    final uri = Uri.parse('$_apiBaseUrl$path');
    final response = await http.delete(uri);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('DELETE $path 失败: ${response.statusCode} ${response.body}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is Map<String, dynamic>) return decoded;
    return {'data': decoded};
  }

  Future<Map<String, dynamic>> _uploadSingleFile(String filename, List<int> bytes, String? mimeType) async {
    final uri = Uri.parse('$_apiBaseUrl/api/documents/upload');
    final request = http.MultipartRequest('POST', uri);
    request.files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename));
    final response = await request.send();
    final body = await response.stream.bytesToString();
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('上传 $filename 失败: ${response.statusCode} $body');
    }
    return jsonDecode(body) as Map<String, dynamic>;
  }

  Future<void> _fetchDocuments({bool resetPage = false}) async {
    if (resetPage) _documentsPage = 1;
    setState(() {
      _isLoadingDocuments = true;
      _isLoadingNotebooks = true;
    });
    try {
      final result = await _apiPost('/api/documents/paginated', body: {
        'page': _documentsPage,
        'page_size': 12,
        'status_filter': _documentsStatusFilter,
        'sort_field': 'updated_at',
        'sort_direction': 'desc',
      });
      final docs = (result['documents'] as List? ?? const [])
          .whereType<Map>()
          .map((entry) => Map<String, dynamic>.from(entry))
          .toList();
      final pagination = Map<String, dynamic>.from(result['pagination'] as Map? ?? {});
      final countsRaw = Map<String, dynamic>.from(result['status_counts'] as Map? ?? {});
      final notebooks = docs.map((doc) {
        final id = _stringOf(doc['id'], fallback: DateTime.now().microsecondsSinceEpoch.toString());
        final title = _shortFileName(_stringOf(doc['file_path'], fallback: id));
        return Notebook(id: id, title: title);
      }).toList();

      if (!mounted) return;
      setState(() {
        _documents = docs;
        _documentsTotal = _intOf(pagination['total_count']);
        _documentsHasNext = pagination['has_next'] == true;
        _documentsHasPrev = pagination['has_prev'] == true;
        _statusCounts = countsRaw.map((k, v) => MapEntry(k, _intOf(v)));
        _notebooks = notebooks;
        if (_selectedDocument != null) {
          final selectedId = _stringOf(_selectedDocument!['id']);
          final refreshed = _documents.firstWhere((d) => _stringOf(d['id']) == selectedId, orElse: () => {});
          _selectedDocument = refreshed.isEmpty ? null : refreshed;
        }
        if (_selectedDocument == null && _documents.isNotEmpty) {
          _selectedDocument = _documents.first;
        }
        _currentNotebook = _selectedDocument == null
            ? null
            : Notebook(
                id: _stringOf(_selectedDocument!['id']),
                title: _shortFileName(_stringOf(_selectedDocument!['file_path'], fallback: 'Untitled')),
              );
        _isLoadingDocuments = false;
        _isLoadingNotebooks = false;
      });
      await _refreshPipelineStatus(silent: true);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _isLoadingDocuments = false;
        _isLoadingNotebooks = false;
      });
      await _showError(error);
    }
  }

  Future<void> _createNewNotebook() async {
    if (_isCreatingNotebook) return;
    setState(() => _isCreatingNotebook = true);
    await Future<void>.delayed(const Duration(milliseconds: 250));
    if (!mounted) return;
    setState(() => _isCreatingNotebook = false);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('后端暂无 Notebook 实体，请通过“添加来源”创建内容')),
    );
  }

  Future<void> _loadDocumentDetail(Map<String, dynamic> doc) async {
    final docId = _stringOf(doc['id']);
    if (docId.isEmpty) return;
    setState(() {
      _selectedDocument = doc;
      _currentNotebook = Notebook(
        id: docId,
        title: _shortFileName(_stringOf(doc['file_path'], fallback: docId)),
      );
      _isLoadingDocumentDetail = true;
      _centerMode = CenterViewMode.document;
    });

    try {
      final detail = await _apiGet('/api/documents/track/$docId');
      final docs = detail['documents'];
      if (docs is List && docs.isNotEmpty && docs.first is Map) {
        _selectedDocument = Map<String, dynamic>.from(docs.first as Map);
      }
    } catch (_) {}

    try {
      final knowledge = await _apiGet('/api/documents/$docId/knowledge');
      final nodes = (knowledge['knowledge_nodes'] as List? ?? const [])
          .whereType<Map>()
          .map((entry) => Map<String, dynamic>.from(entry))
          .toList();
      if (!mounted) return;
      setState(() {
        _documentKnowledgeNodes = nodes;
        _isLoadingDocumentDetail = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _isLoadingDocumentDetail = false);
      await _showError(error);
    }
  }

  Future<void> _deleteDocument(Map<String, dynamic> doc) async {
    final docId = _stringOf(doc['id']);
    if (docId.isEmpty) return;
    try {
      await _apiDelete('/api/documents/$docId');
      if (_selectedDocument != null && _stringOf(_selectedDocument!['id']) == docId) {
        setState(() {
          _selectedDocument = null;
          _documentKnowledgeNodes = [];
          if (_centerMode == CenterViewMode.document) {
            _centerMode = CenterViewMode.chat;
          }
        });
      }
      await _fetchDocuments();
      await _refreshSkillNodes();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('文档已删除')));
    } catch (error) {
      await _showError(error);
    }
  }

  Future<void> _refreshSkillNodes() async {
    setState(() => _isLoadingSkillNodes = true);
    try {
      final result = await _apiGetList('/api/skill-tree/nodes');
      final nodes = result.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
      if (!mounted) return;
      setState(() {
        _skillNodes = nodes;
        _isLoadingSkillNodes = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _isLoadingSkillNodes = false);
      await _showError(error);
    }
  }

  Future<void> _startLearning(Map<String, dynamic> node) async {
    final nodeId = _stringOf(node['id']);
    if (nodeId.isEmpty) return;
    try {
      final result = await _apiGet('/api/skill-tree/nodes/$nodeId/learning-content');
      if (!mounted) return;
      setState(() {
        _learningNodeName = _stringOf(node['name'], fallback: '学习内容');
        _learningContent = _stringOf(result['content'], fallback: '未返回学习内容');
        _centerMode = CenterViewMode.learning;
      });
      await _refreshSkillNodes();
    } catch (error) {
      await _showError(error);
    }
  }

  Future<void> _completeLearning(Map<String, dynamic> node) async {
    final nodeId = _stringOf(node['id']);
    if (nodeId.isEmpty) return;
    try {
      await _apiPost('/api/skill-tree/nodes/$nodeId/complete');
      await _refreshSkillNodes();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('已标记为完成')));
    } catch (error) {
      await _showError(error);
    }
  }

  Future<void> _generateQuizForNode(Map<String, dynamic> node) async {
    final nodeId = _stringOf(node['id']);
    if (nodeId.isEmpty) return;
    setState(() {
      _isGeneratingQuiz = true;
      _quizNodeId = nodeId;
    });
    try {
      final result = await _apiGet('/api/quiz/generate/$nodeId', query: {'num_questions': '$_quizQuestionCount'});
      final questions = (result['questions'] as List? ?? const [])
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList();
      if (!mounted) return;
      setState(() {
        _quizNodeId = nodeId;
        _quizNodeName = _stringOf(result['node_name'], fallback: _stringOf(node['name']));
        _quizQuestions = questions;
        _quizAnswers = {};
        _quizResult = null;
        _centerMode = CenterViewMode.quiz;
        _isGeneratingQuiz = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _isGeneratingQuiz = false);
      await _showError(error);
    }
  }

  Future<void> _submitQuiz() async {
    if (_quizNodeId == null || _quizQuestions.isEmpty) return;
    if (_quizAnswers.length < _quizQuestions.length) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('请先回答所有题目')));
      return;
    }
    setState(() => _isSubmittingQuiz = true);
    try {
      final result = await _apiPost('/api/quiz/submit/${_quizNodeId!}', body: {
        'questions': _quizQuestions,
        'user_answers': _quizAnswers,
      });
      if (!mounted) return;
      setState(() {
        _quizResult = Map<String, dynamic>.from(result);
        _isSubmittingQuiz = false;
      });
      await _refreshSkillNodes();
    } catch (error) {
      if (!mounted) return;
      setState(() => _isSubmittingQuiz = false);
      await _showError(error);
    }
  }

  Future<void> _switchNotebook(Notebook nb) async {
    final doc = _documents.firstWhere((d) => _stringOf(d['id']) == nb.id, orElse: () => {});
    if (doc.isNotEmpty) await _loadDocumentDetail(doc);
    if (!mounted) return;
    _scaffoldKey.currentState?.closeDrawer();
  }

  Future<void> _pickFile() async {
    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(allowMultiple: true, withData: true);
      if (result != null) {
        setState(() => _isUploading = true);
        final uploadedNames = <String>[];
        var failedCount = 0;
        for (final file in result.files) {
          final bytes = file.bytes;
          if (bytes == null || bytes.isEmpty) {
            failedCount += 1;
            continue;
          }
          try {
            await _uploadSingleFile(file.name, bytes, file.extension);
            uploadedNames.add(file.name);
          } catch (_) {
            failedCount += 1;
          }
        }
        await _fetchDocuments(resetPage: true);
        await _refreshSkillNodes();
        if (!mounted) return;
        setState(() {
          _isUploading = false;
          if (uploadedNames.isNotEmpty) {
            _messages.add(ChatMessage(text: "✅ 已成功上传并解析: ${uploadedNames.join(', ')}", isUser: true));
          }
          if (failedCount > 0) {
            _messages.add(ChatMessage(text: "⚠️ $failedCount 个文件上传失败，请检查后端或 LightRAG 状态。", isUser: false));
          }
        });
        _scrollToBottom();
        if (uploadedNames.isNotEmpty) {
          _simulateBackendResponse("文件已接收并入库。你现在可以直接提问文档内容。");
        }
      }
    } catch (e) {
      setState(() => _isUploading = false);
      debugPrint("文件选择出错: $e");
    }
  }

  void _sendMessage() {
    final text = _chatController.text.trim();
    if (text.isEmpty) return;
    setState(() {
      _messages.add(ChatMessage(text: text, isUser: true));
      _chatController.clear();
      _isThinking = true;
      _centerMode = CenterViewMode.chat;
    });
    _scrollToBottom();
    _queryAssistant(text);
  }

  Future<void> _queryAssistant(String text) async {
    try {
      final result = await _apiGet('/api/learning/query', query: {
        'query': text,
        'mode': _qaMode,
        'include_references': _includeReferences ? 'true' : 'false',
      });
      final reply = (result['response'] ?? '').toString();
      final refs = (result['references'] as List? ?? const [])
          .whereType<Map>()
          .map((entry) => _shortFileName(_stringOf(entry['file_path'], fallback: 'Unknown')))
          .toList();
      if (!mounted) return;
      setState(() {
        _isThinking = false;
        _messages.add(ChatMessage(text: reply.isEmpty ? '后端已响应，但未返回内容。' : reply, isUser: false, references: refs));
      });
      _scrollToBottom();
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isThinking = false;
        _messages.add(ChatMessage(text: "请求失败：$e", isUser: false));
      });
      _scrollToBottom();
    }
  }

  Future<void> _simulateBackendResponse(String responseText) async {
    await Future.delayed(const Duration(milliseconds: 1500));
    if (mounted) {
      setState(() {
        _isThinking = false;
        _messages.add(ChatMessage(text: responseText, isUser: false));
      });
      _scrollToBottom();
    }
  }

  String _resolveGraphLabel() {
    if (_selectedDocument != null) {
      final path = _stringOf(_selectedDocument!['file_path']);
      final shortName = _shortFileName(path);
      if (shortName.isNotEmpty) return shortName.replaceAll(RegExp(r'\.[^.]+$'), '');
    }
    for (var index = _messages.length - 1; index >= 0; index -= 1) {
      final msg = _messages[index];
      if (msg.isUser && msg.text.trim().isNotEmpty) return msg.text.trim();
    }
    return 'knowledge';
  }

  String _studioActionLabel(String action) {
    const mapping = {
      'audio_overview': '音频概览', 'video_overview': '视频概览', 'mindmap': '思维导图',
      'report': '报告', 'flashcards': '闪卡', 'quiz': '测验',
      'infographic': '信息图', 'presentation': '演示文稿', 'table': '数据表格',
    };
    return mapping[action] ?? action;
  }

  Future<void> _handleStudioAction(String action) async {
    if (_isGeneratingStudio) return;
    setState(() {
      _isGeneratingStudio = true;
      _activeStudioTool = _studioActionLabel(action);
    });

    try {
      if (action == 'mindmap' || action == 'infographic') {
        final label = _resolveGraphLabel();
        final graphResult = await _apiGet('/api/learning/graph', query: {
          'label': label, 'max_depth': '3', 'max_nodes': action == 'infographic' ? '80' : '120',
        });
        if (!mounted) return;
        setState(() {
          _isGeneratingStudio = false; _activeStudioTool = null;
          _studioGraphPayload = graphResult; _studioGraphLabel = label;
          _centerMode = CenterViewMode.studioGraph;
        });
        return;
      }

      final topic = _resolveGraphLabel();
      final result = await _apiPost('/api/learning/studio/generate', body: {
        'action': action, 'topic': topic, 'mode': _qaMode,
      });

      final reply = (result['content'] ?? '').toString();
      final note = (result['capability_note'] ?? '').toString();

      if (!mounted) return;
      setState(() {
        _isGeneratingStudio = false; _activeStudioTool = null;
        _studioTextTitle = (result['title'] ?? _studioActionLabel(action)).toString();
        _studioTextType = (result['delivery_type'] ?? '').toString();
        _studioTextTopic = (result['topic'] ?? topic).toString();
        _studioTextContent = reply.isEmpty ? '（模型未返回正文）' : '$note\n\n$reply';
        _centerMode = CenterViewMode.studioText;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isGeneratingStudio = false; _activeStudioTool = null;
      });
      await _showError(e);
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300), curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    
    return Scaffold(
      key: _scaffoldKey,
      backgroundColor: colorScheme.surface,
      drawer: _buildDrawer(context), 
      body: Column(
        children: [
          _buildTopAppBar(context),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(left: 12.0, right: 12.0, bottom: 12.0),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Expanded(flex: 2, child: _buildLeftPanel(context)),
                  const SizedBox(width: 12),
                  Expanded(flex: 5, child: _buildCenterPanel(context)),
                  const SizedBox(width: 12),
                  Expanded(flex: 3, child: _buildRightPanel(context)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTopAppBar(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Container(
      height: 60,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          IconButton(
            icon: Icon(Icons.menu, color: colorScheme.onSurfaceVariant),
            onPressed: () => _scaffoldKey.currentState?.openDrawer(),
          ),
          const SizedBox(width: 8),
          CircleAvatar(
            radius: 14,
            backgroundColor: colorScheme.secondaryContainer,
            child: Icon(Icons.view_cozy_outlined, size: 16, color: colorScheme.onSecondaryContainer),
          ),
          const SizedBox(width: 12),
          Text(
            _isLoadingNotebooks ? "加载中..." : (_currentNotebook?.title ?? "Untitled notebook"),
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w500, color: colorScheme.onSurface),
          ),
          const Spacer(),
          _buildTopButton(context, Icons.add, _isCreatingNotebook ? "创建中..." : "创建笔记本", onTap: _createNewNotebook, isLoading: _isCreatingNotebook),
          const SizedBox(width: 8),
          _buildTopButton(context, Icons.description_outlined, "文档", onTap: () => setState(() => _centerMode = CenterViewMode.document)),
          const SizedBox(width: 8),
          _buildTopButton(context, Icons.school_outlined, "学习", onTap: () => setState(() => _centerMode = CenterViewMode.learning)),
          const SizedBox(width: 8),
          _buildTopButton(context, Icons.quiz_outlined, "测验", onTap: () => setState(() => _centerMode = CenterViewMode.quiz)),
          const SizedBox(width: 8),
          _buildTopButton(context, Icons.hub_outlined, "图谱", onTap: () => setState(() => _centerMode = CenterViewMode.studioGraph)),
          const SizedBox(width: 12),
          
          IconButton(
            icon: Icon(
              isDark ? Icons.light_mode : Icons.dark_mode_outlined, 
              color: colorScheme.onSurfaceVariant,
              size: 20,
            ),
            onPressed: () {
              themeNotifier.value = isDark ? ThemeMode.light : ThemeMode.dark;
            },
            tooltip: '切换主题',
          ),
          
          const SizedBox(width: 8),
          Icon(Icons.grid_view_outlined, color: colorScheme.onSurfaceVariant),
          const SizedBox(width: 16),
          CircleAvatar(
            radius: 16,
            backgroundColor: colorScheme.primary,
            child: Icon(Icons.person_outline, size: 20, color: colorScheme.onPrimary),
          ),
        ],
      ),
    );
  }

  Widget _buildTopButton(BuildContext context, IconData icon, String label, {VoidCallback? onTap, bool isLoading = false}) {
    // 使用 Material 3 原生的 Tonal Button (最适合这种次级导航动作)
    return FilledButton.tonalIcon(
      onPressed: isLoading ? null : onTap,
      icon: isLoading
          ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
          : Icon(icon, size: 16),
      label: Text(label, style: const TextStyle(fontSize: 13)),
      style: FilledButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        minimumSize: Size.zero,
      ),
    );
  }

  Widget _buildDrawer(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Drawer(
      backgroundColor: colorScheme.surfaceContainerLow,
      child: Column(
        children: [
          Container(
            height: 120,
            alignment: Alignment.bottomLeft,
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              border: Border(bottom: BorderSide(color: colorScheme.outlineVariant)),
            ),
            child: Text(
              "我的笔记本",
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: colorScheme.onSurface),
            ),
          ),
          Expanded(
            child: _isLoadingNotebooks
                ? Center(child: CircularProgressIndicator(color: colorScheme.primary))
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    itemCount: _notebooks.length,
                    itemBuilder: (context, index) {
                      final nb = _notebooks[index];
                      final isSelected = nb.id == _currentNotebook?.id;
                      return Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        child: ListTile(
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          leading: Icon(Icons.menu_book_rounded, color: isSelected ? colorScheme.primary : colorScheme.onSurfaceVariant),
                          title: Text(
                            nb.title, 
                            style: TextStyle(
                              color: isSelected ? colorScheme.primary : colorScheme.onSurface,
                              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                            ),
                          ),
                          selected: isSelected,
                          selectedTileColor: colorScheme.secondaryContainer,
                          onTap: () => _switchNotebook(nb),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildLeftPanel(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: colorScheme.outlineVariant),
      ),
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text("来源", style: TextStyle(fontSize: 16, fontWeight: FontWeight.w500, color: colorScheme.onSurface)),
              Icon(Icons.view_sidebar_outlined, color: colorScheme.onSurfaceVariant, size: 20),
            ],
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _isUploading ? null : _pickFile,
              icon: _isUploading
                  ? SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: colorScheme.primary))
                  : const Icon(Icons.add, size: 18),
              label: Text(_isUploading ? "正在上传解析..." : "添加来源"),
              style: OutlinedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
              ),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<String?>(
                  value: _documentsStatusFilter,
                  dropdownColor: colorScheme.surfaceContainerHighest,
                  decoration: InputDecoration(
                    isDense: true,
                    filled: true,
                    fillColor: colorScheme.surfaceContainerHighest,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
                  ),
                  items: [
                    DropdownMenuItem(value: null, child: Text('全部状态', style: TextStyle(color: colorScheme.onSurface))),
                    DropdownMenuItem(value: 'processed', child: Text('已处理', style: TextStyle(color: colorScheme.onSurface))),
                    DropdownMenuItem(value: 'processing', child: Text('处理中', style: TextStyle(color: colorScheme.onSurface))),
                    DropdownMenuItem(value: 'pending', child: Text('等待中', style: TextStyle(color: colorScheme.onSurface))),
                    DropdownMenuItem(value: 'failed', child: Text('失败', style: TextStyle(color: colorScheme.onSurface))),
                    DropdownMenuItem(value: 'preprocessed', child: Text('预处理', style: TextStyle(color: colorScheme.onSurface))),
                  ],
                  onChanged: (value) async {
                    setState(() => _documentsStatusFilter = value);
                    await _fetchDocuments(resetPage: true);
                  },
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filledTonal(
                onPressed: () async {
                  await _fetchDocuments();
                  await _refreshPipelineStatus(silent: true);
                },
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Text('共 $_documentsTotal 条', style: TextStyle(color: colorScheme.onSurfaceVariant, fontSize: 12)),
              const Spacer(),
              TextButton.icon(
                onPressed: () async => await _refreshPipelineStatus(),
                icon: const Icon(Icons.sync, size: 14),
                label: const Text('队列', style: TextStyle(fontSize: 11)),
              ),
            ],
          ),
          const SizedBox(height: 4),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _buildStatusMetricCard(context, 'processed', '已处理'),
                const SizedBox(width: 8),
                _buildStatusMetricCard(context, 'processing', '处理中'),
                const SizedBox(width: 8),
                _buildStatusMetricCard(context, 'pending', '等待中'),
                const SizedBox(width: 8),
                _buildStatusMetricCard(context, 'failed', '失败'),
                const SizedBox(width: 8),
                _buildStatusMetricCard(context, 'preprocessed', '预处理'),
              ],
            ),
          ),
          const SizedBox(height: 8),
          _buildPipelineCard(context),
          const SizedBox(height: 8),
          Expanded(
            child: _isLoadingDocuments
                ? Center(child: CircularProgressIndicator(color: colorScheme.primary))
                : _documents.isEmpty
                    ? Center(child: Text('暂无文档来源', style: TextStyle(color: colorScheme.onSurfaceVariant.withOpacity(0.6))))
                    : ListView.builder(
                        itemCount: _documents.length,
                        itemBuilder: (context, index) {
                          final doc = _documents[index];
                          final docId = _stringOf(doc['id']);
                          final selected = _selectedDocument != null && _stringOf(_selectedDocument!['id']) == docId;
                          final status = _stringOf(doc['status'], fallback: 'pending');
                          return Card(
                            elevation: 0,
                            margin: const EdgeInsets.only(bottom: 8),
                            color: selected ? colorScheme.secondaryContainer : colorScheme.surfaceContainer,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                              side: BorderSide(color: selected ? colorScheme.primary : colorScheme.outlineVariant),
                            ),
                            child: Padding(
                              padding: const EdgeInsets.all(10),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    _shortFileName(_stringOf(doc['file_path'], fallback: '未命名文档')),
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: selected ? colorScheme.onSecondaryContainer : colorScheme.onSurface),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(_statusText(status), style: TextStyle(fontSize: 11, color: _statusColor(status, colorScheme))),
                                  const SizedBox(height: 8),
                                  Row(
                                    children: [
                                      Expanded(
                                        child: OutlinedButton(
                                          onPressed: () => _loadDocumentDetail(doc),
                                          style: OutlinedButton.styleFrom(
                                            padding: EdgeInsets.zero,
                                            minimumSize: const Size(0, 32),
                                          ),
                                          child: const Text('查看', style: TextStyle(fontSize: 11)),
                                        ),
                                      ),
                                      const SizedBox(width: 6),
                                      Expanded(
                                        child: OutlinedButton(
                                          onPressed: () => _deleteDocument(doc),
                                          style: OutlinedButton.styleFrom(
                                            padding: EdgeInsets.zero,
                                            minimumSize: const Size(0, 32),
                                          ),
                                          child: const Text('删除', style: TextStyle(fontSize: 11)),
                                        ),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
          ),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: _documentsHasPrev ? () async { _documentsPage -= 1; await _fetchDocuments(); } : null,
                  child: const Text('上一页'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton(
                  onPressed: _documentsHasNext ? () async { _documentsPage += 1; await _fetchDocuments(); } : null,
                  child: const Text('下一页'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildCenterPanel(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: colorScheme.outlineVariant),
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Row(
              children: [
                Text("工作区", style: TextStyle(fontSize: 16, fontWeight: FontWeight.w500, color: colorScheme.onSurface)),
                const Spacer(),
                Wrap(
                  spacing: 8,
                  children: [
                    _modeChip(context, '对话', _centerMode == CenterViewMode.chat, () => setState(() => _centerMode = CenterViewMode.chat)),
                    _modeChip(context, '文档', _centerMode == CenterViewMode.document, () => setState(() => _centerMode = CenterViewMode.document)),
                    _modeChip(context, '学习', _centerMode == CenterViewMode.learning, () => setState(() => _centerMode = CenterViewMode.learning)),
                    _modeChip(context, '测验', _centerMode == CenterViewMode.quiz, () => setState(() => _centerMode = CenterViewMode.quiz)),
                    _modeChip(context, '图谱', _centerMode == CenterViewMode.studioGraph, () => setState(() => _centerMode = CenterViewMode.studioGraph)),
                    _modeChip(context, 'Studio', _centerMode == CenterViewMode.studioText, () => setState(() => _centerMode = CenterViewMode.studioText)),
                  ],
                ),
              ],
            ),
          ),
          Expanded(child: _buildCenterBody(context)),
          if (_centerMode == CenterViewMode.chat) _buildChatInputArea(context),
        ],
      ),
    );
  }

  Widget _modeChip(BuildContext context, String label, bool selected, VoidCallback onTap) {
    return ChoiceChip(
      label: Text(label, style: const TextStyle(fontSize: 12)),
      selected: selected,
      onSelected: (_) => onTap(),
      showCheckmark: false,
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 0),
    );
  }

  Widget _buildStatusMetricCard(BuildContext context, String key, String label) {
    final colorScheme = Theme.of(context).colorScheme;
    final count = _statusCounts[key] ?? 0;
    final color = _statusColor(key, colorScheme);
    return Card(
      elevation: 0,
      color: colorScheme.surfaceContainer,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: colorScheme.outlineVariant),
      ),
      child: Container(
        width: 96,
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(_statusIcon(key), size: 14, color: color),
                const SizedBox(width: 4),
                Expanded(child: Text(label, maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 11, color: colorScheme.onSurfaceVariant))),
              ],
            ),
            const SizedBox(height: 6),
            Text('$count', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: colorScheme.onSurface)),
          ],
        ),
      ),
    );
  }

  Widget _buildPipelineCard(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final pipeline = _pipelineStatus;
    
    if (pipeline == null || pipeline.isEmpty) {
      return Card(
        elevation: 0,
        color: colorScheme.surfaceContainer,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10), side: BorderSide(color: colorScheme.outlineVariant)),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(10),
          child: Text('暂无处理队列状态', style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant)),
        ),
      );
    }
    
    final busy = pipeline['busy'] == true;
    final curBatch = _intOf(pipeline['cur_batch']);
    final totalBatch = _intOf(pipeline['batchs'], fallback: 1);
    final progress = totalBatch <= 0 ? 0.0 : (curBatch / totalBatch).clamp(0.0, 1.0);
    final jobName = _stringOf(pipeline['job_name'], fallback: '未知任务');
    final message = _stringOf(pipeline['latest_message'], fallback: '');

    return Card(
      elevation: 0,
      color: colorScheme.surfaceContainer,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10), side: BorderSide(color: colorScheme.outlineVariant)),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(busy ? Icons.sync : Icons.check_circle, size: 14, color: busy ? Colors.orange : Colors.green),
                const SizedBox(width: 6),
                Expanded(child: Text(busy ? '处理中：$jobName' : '处理队列空闲', maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: colorScheme.onSurface))),
                if (busy) Text('$curBatch/$totalBatch', style: TextStyle(fontSize: 11, color: colorScheme.onSurfaceVariant)),
              ],
            ),
            const SizedBox(height: 8),
            LinearProgressIndicator(
              value: busy ? progress : 1,
              minHeight: 6,
              backgroundColor: colorScheme.surfaceContainerHighest,
              color: busy ? Colors.orange : Colors.green,
              borderRadius: BorderRadius.circular(3),
            ),
            if (message.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(message, maxLines: 2, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 11, color: colorScheme.onSurfaceVariant)),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildCenterBody(BuildContext context) {
    switch (_centerMode) {
      case CenterViewMode.document: return _buildDocumentDetailView(context);
      case CenterViewMode.learning: return _buildLearningView(context);
      case CenterViewMode.quiz: return _buildQuizView(context);
      case CenterViewMode.studioGraph: return _buildStudioGraphView(context);
      case CenterViewMode.studioText: return _buildStudioTextView(context);
      case CenterViewMode.chat: default: return _buildChatView(context);
    }
  }

  List<Map<String, dynamic>> _asMapList(dynamic value) {
    if (value is List) return value.whereType<Map>().map((item) => Map<String, dynamic>.from(item)).toList();
    return const [];
  }

  String _readStringByKeys(Map<String, dynamic> data, List<String> keys) {
    for (final key in keys) {
      final value = data[key];
      if (value != null && value.toString().trim().isNotEmpty) return value.toString().trim();
    }
    return '';
  }

  Map<String, dynamic> _getGraphRoot(dynamic payload) {
    if (payload is Map<String, dynamic>) {
      final graph = payload['graph'];
      if (graph is Map) return Map<String, dynamic>.from(graph);
      return payload;
    }
    return {};
  }

  List<_GraphNodeVm> _extractGraphNodes(Map<String, dynamic> graphRoot) {
    dynamic rawNodes;
    for (final key in ['nodes', 'vertices', 'entities', 'items']) {
      if (graphRoot.containsKey(key)) { rawNodes = graphRoot[key]; break; }
    }
    final parsed = <_GraphNodeVm>[];
    final seen = <String>{};
    for (final item in _asMapList(rawNodes)) {
      final id = _readStringByKeys(item, ['id', 'node_id', 'name', 'label', 'entity']);
      if (id.isEmpty || seen.contains(id)) continue;
      seen.add(id);
      final label = _readStringByKeys(item, ['label', 'name', 'entity', 'title']);
      parsed.add(_GraphNodeVm(id: id, label: label.isEmpty ? id : label));
    }
    return parsed;
  }

  List<_GraphEdgeVm> _extractGraphEdges(Map<String, dynamic> graphRoot) {
    dynamic rawEdges;
    for (final key in ['edges', 'links', 'relations', 'relationships']) {
      if (graphRoot.containsKey(key)) { rawEdges = graphRoot[key]; break; }
    }
    final parsed = <_GraphEdgeVm>[];
    for (final item in _asMapList(rawEdges)) {
      final source = _readStringByKeys(item, ['source', 'from', 'src', 'start', 'head']);
      final target = _readStringByKeys(item, ['target', 'to', 'dst', 'end', 'tail']);
      if (source.isEmpty || target.isEmpty) continue;
      final label = _readStringByKeys(item, ['label', 'type', 'relation', 'name']);
      parsed.add(_GraphEdgeVm(source: source, target: target, label: label));
    }
    return parsed;
  }

  Future<void> _exportGraphAsPng() async {
    if (_isExportingGraph) return;
    setState(() => _isExportingGraph = true);

    try {
      final boundary = _graphExportKey.currentContext?.findRenderObject() as RenderRepaintBoundary?;
      if (boundary == null) throw Exception('未找到可导出的图谱画布。');
      final ui.Image image = await boundary.toImage(pixelRatio: 2.5);
      final byteData = await image.toByteData(format: ui.ImageByteFormat.png);
      if (byteData == null) throw Exception('图谱导出失败：无法生成图片字节流。');
      final bytes = byteData.buffer.asUint8List();
      final ts = DateTime.now().toIso8601String().replaceAll(':', '-');
      final filename = 'knowledge_graph_${_studioGraphLabel ?? 'export'}_$ts.png';

      final saveResult = await FilePicker.platform.saveFile(
        dialogTitle: '导出知识图谱', fileName: filename, bytes: bytes,
      );

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(saveResult == null ? '已取消导出' : '导出成功：$filename')),
      );
    } catch (error) {
      if (!mounted) return;
      await _showError(error);
    } finally {
      if (mounted) setState(() => _isExportingGraph = false);
    }
  }

  Widget _buildStudioTextView(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final title = (_studioTextTitle ?? '').trim();
    final topic = (_studioTextTopic ?? '').trim();
    final type = (_studioTextType ?? '').trim();
    final content = (_studioTextContent ?? '').trim();

    if (content.isEmpty) {
      return Center(
        child: Text('请在右侧 Studio 选择“报告 / 闪卡 / 测验 / 演示文稿 / 表格 / 音频 / 视频”生成文本结果',
          style: TextStyle(color: colorScheme.onSurfaceVariant), textAlign: TextAlign.center,
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title.isEmpty ? 'Studio 输出' : title, style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: colorScheme.onSurface)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8, runSpacing: 8,
            children: [
              if (type.isNotEmpty) _buildMetaTag(context, '类型: $type'),
              if (topic.isNotEmpty) _buildMetaTag(context, '主题: $topic'),
            ],
          ),
          const SizedBox(height: 12),
          Expanded(
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: colorScheme.surfaceContainer,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: colorScheme.outlineVariant),
              ),
              child: SingleChildScrollView(
                child: SelectableText(content, style: TextStyle(fontSize: 14, height: 1.5, color: colorScheme.onSurface)),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMetaTag(BuildContext context, String text) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(color: colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(999)),
      child: Text(text, style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant)),
    );
  }

  Widget _buildStudioGraphView(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final payload = _studioGraphPayload;
    if (payload == null) {
      return Center(
        child: Text('请在右侧 Studio 点击「思维导图」或「信息图」生成图谱', style: TextStyle(color: colorScheme.onSurfaceVariant)),
      );
    }

    final graphRoot = _getGraphRoot(payload);
    final nodes = _extractGraphNodes(graphRoot);
    final edges = _extractGraphEdges(graphRoot);

    if (nodes.isEmpty) {
      return Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('图谱结果为空（label: ${_studioGraphLabel ?? ''}）', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: colorScheme.onSurface)),
            const SizedBox(height: 8),
            Text('可尝试先上传文档并等待 LightRAG 处理完成，再重新生成。', style: TextStyle(color: colorScheme.onSurfaceVariant)),
          ],
        ),
      );
    }

    final size = const Size(1200, 760);
    final positions = _layoutCircular(nodes, size);

    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
            child: Row(
              children: [
                Expanded(
                  child: Text('知识图谱：${_studioGraphLabel ?? ''}（节点 ${nodes.length} / 边 ${edges.length}）',
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: colorScheme.onSurface),
                  ),
                ),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  onPressed: _isExportingGraph ? null : _exportGraphAsPng,
                  icon: _isExportingGraph
                      ? const SizedBox(width: 12, height: 12, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.download_outlined, size: 16),
                  label: const Text('导出 PNG'),
                ),
              ],
            ),
          ),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Container(
                color: colorScheme.surfaceContainer,
                child: InteractiveViewer(
                  minScale: 0.3, maxScale: 4, constrained: false,
                  child: RepaintBoundary(
                    key: _graphExportKey,
                    child: CustomPaint(
                      size: size,
                      painter: _KnowledgeGraphPainter(
                        nodes: nodes, 
                        edges: edges, 
                        positions: positions, 
                        colorScheme: colorScheme,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Map<String, Offset> _layoutCircular(List<_GraphNodeVm> nodes, Size size) {
    final map = <String, Offset>{};
    if (nodes.isEmpty) return map;
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) * 0.36;
    for (var index = 0; index < nodes.length; index += 1) {
      final angle = (2 * math.pi * index) / nodes.length;
      map[nodes[index].id] = Offset(center.dx + radius * math.cos(angle), center.dy + radius * math.sin(angle));
    }
    return map;
  }

  Widget _buildChatView(BuildContext context) {
    if (_messages.isEmpty) return _buildEmptyChatState(context);
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      itemCount: _messages.length + (_isThinking ? 1 : 0),
      itemBuilder: (context, index) {
        if (index == _messages.length) return _buildThinkingBubble(context);
        return _buildChatBubble(context, _messages[index]);
      },
    );
  }

  Widget _buildDocumentDetailView(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    if (_selectedDocument == null) {
      return Center(child: Text('请在左侧选择文档', style: TextStyle(color: colorScheme.onSurfaceVariant)));
    }
    if (_isLoadingDocumentDetail) {
      return Center(child: CircularProgressIndicator(color: colorScheme.primary));
    }
    final doc = _selectedDocument!;
    final status = _stringOf(doc['status'], fallback: 'pending');
    return ListView(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      children: [
        Text(_shortFileName(_stringOf(doc['file_path'], fallback: '未命名文档')), style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600, color: colorScheme.onSurface)),
        const SizedBox(height: 8),
        Text('ID: ${_stringOf(doc['id'])}', style: TextStyle(color: colorScheme.onSurfaceVariant)),
        const SizedBox(height: 4),
        Text('状态: ${_statusText(status)}', style: TextStyle(color: _statusColor(status, colorScheme))),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(child: _metricCard(context, '长度', '${_intOf(doc['content_length'])} 字符')),
            const SizedBox(width: 8),
            Expanded(child: _metricCard(context, '分块', '${_intOf(doc['chunks_count'])}')),
            const SizedBox(width: 8),
            Expanded(child: _metricCard(context, '更新', _stringOf(doc['updated_at']).replaceFirst('T', ' ').split('.').first)),
          ],
        ),
        const SizedBox(height: 16),
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: colorScheme.surfaceContainer, borderRadius: BorderRadius.circular(12), border: Border.all(color: colorScheme.outlineVariant)),
          child: Text(_stringOf(doc['content_summary'], fallback: '暂无摘要'), style: TextStyle(height: 1.4, color: colorScheme.onSurface)),
        ),
        const SizedBox(height: 16),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('关联知识点', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: colorScheme.onSurface)),
            Text('${_documentKnowledgeNodes.length} 个', style: TextStyle(color: colorScheme.onSurfaceVariant)),
          ],
        ),
        const SizedBox(height: 8),
        if (_documentKnowledgeNodes.isEmpty)
          Text('暂无知识点', style: TextStyle(color: colorScheme.onSurfaceVariant.withOpacity(0.6)))
        else
          ..._documentKnowledgeNodes.take(20).map((n) => _knowledgeNodeTile(context, n)),
      ],
    );
  }

  Widget _knowledgeNodeTile(BuildContext context, Map<String, dynamic> node) {
    final colorScheme = Theme.of(context).colorScheme;
    final mastery = _doubleOf(node['mastery']);
    final status = _stringOf(node['status']);
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 8),
      color: colorScheme.surfaceContainer,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10), side: BorderSide(color: colorScheme.outlineVariant)),
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_stringOf(node['name'], fallback: '未命名知识点'), style: TextStyle(fontWeight: FontWeight.w600, color: colorScheme.onSurface)),
            const SizedBox(height: 4),
            Text(_stringOf(node['description'], fallback: '暂无描述'), style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant)),
            const SizedBox(height: 6),
            LinearProgressIndicator(
              value: (mastery.clamp(0, 100)) / 100, 
              minHeight: 6,
              backgroundColor: colorScheme.surfaceContainerHighest, 
              color: colorScheme.primary,
              borderRadius: BorderRadius.circular(3),
            ),
            const SizedBox(height: 4),
            Text('${_statusText(status)} · ${mastery.toStringAsFixed(1)}%', style: TextStyle(fontSize: 11, color: _statusColor(status, colorScheme))),
          ],
        ),
      ),
    );
  }

  Widget _metricCard(BuildContext context, String label, String value) {
    final colorScheme = Theme.of(context).colorScheme;
    return Card(
      elevation: 0,
      color: colorScheme.surfaceContainer,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10), side: BorderSide(color: colorScheme.outlineVariant)),
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: TextStyle(fontSize: 11, color: colorScheme.onSurfaceVariant)),
            const SizedBox(height: 4),
            Text(value, maxLines: 2, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 13, color: colorScheme.onSurface)),
          ],
        ),
      ),
    );
  }

  Widget _buildLearningView(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    if (_learningContent == null || _learningContent!.isEmpty) {
      return Center(child: Text('请在右侧技能树点击“学习”', style: TextStyle(color: colorScheme.onSurfaceVariant)));
    }
    return ListView(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      children: [
        Text(_learningNodeName ?? '学习内容', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600, color: colorScheme.onSurface)),
        const SizedBox(height: 12),
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(color: colorScheme.surfaceContainer, borderRadius: BorderRadius.circular(12), border: Border.all(color: colorScheme.outlineVariant)),
          child: Text(_learningContent!, style: TextStyle(height: 1.45, color: colorScheme.onSurface)),
        ),
      ],
    );
  }

  Widget _buildQuizView(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    if (_quizQuestions.isEmpty) {
      return Center(child: Text('请在右侧技能树点击“出题”', style: TextStyle(color: colorScheme.onSurfaceVariant)));
    }
    return ListView(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
      children: [
        Text('测验：${_quizNodeName ?? ''}', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: colorScheme.onSurface)),
        const SizedBox(height: 10),
        ..._quizQuestions.asMap().entries.map((entry) {
          final index = entry.key;
          final question = entry.value;
          final qid = _stringOf(question['id'], fallback: 'q$index');
          final qType = _stringOf(question['type'], fallback: 'short_answer');
          final title = _stringOf(question['question'], fallback: '未提供题干');
          return Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: colorScheme.surfaceContainer, borderRadius: BorderRadius.circular(12), border: Border.all(color: colorScheme.outlineVariant)),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Q${index + 1}. $title', style: TextStyle(fontWeight: FontWeight.w600, color: colorScheme.onSurface)),
                const SizedBox(height: 8),
                if (qType == 'multiple_choice')
                  ...(question['options'] as List? ?? const []).map(
                    (option) => RadioListTile<String>(
                      dense: true, value: option.toString(), groupValue: _quizAnswers[qid]?.toString(),
                      onChanged: (value) { if (value != null) setState(() => _quizAnswers[qid] = value); },
                      title: Text(option.toString(), style: TextStyle(fontSize: 13, color: colorScheme.onSurface)),
                    ),
                  )
                else if (qType == 'true_false')
                  ...['对', '错'].map(
                    (option) => RadioListTile<String>(
                      dense: true, value: option, groupValue: _quizAnswers[qid]?.toString(),
                      onChanged: (value) { if (value != null) setState(() => _quizAnswers[qid] = value); },
                      title: Text(option, style: TextStyle(fontSize: 13, color: colorScheme.onSurface)),
                    ),
                  )
                else
                  TextField(
                    onChanged: (value) => _quizAnswers[qid] = value.trim(),
                    maxLines: 3, style: TextStyle(color: colorScheme.onSurface),
                    decoration: InputDecoration(
                      hintText: '输入你的答案', hintStyle: TextStyle(color: colorScheme.onSurfaceVariant.withOpacity(0.6)),
                      filled: true, fillColor: colorScheme.surfaceContainerHighest,
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
                    ),
                  ),
              ],
            ),
          );
        }),
        SizedBox(
          width: double.infinity,
          child: FilledButton.icon(
            onPressed: _isSubmittingQuiz ? null : _submitQuiz,
            icon: _isSubmittingQuiz
                ? SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: colorScheme.onPrimary))
                : const Icon(Icons.check),
            label: const Text('提交测验'),
            style: FilledButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 16),
            ),
          ),
        ),
        if (_quizResult != null) ...[
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: colorScheme.surfaceContainer, borderRadius: BorderRadius.circular(12), border: Border.all(color: colorScheme.outlineVariant)),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('得分：${_doubleOf((_quizResult!['grading_result'] as Map?)?['score']).toStringAsFixed(1)}%',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: colorScheme.onSurface),
                ),
                const SizedBox(height: 6),
                Text('状态：${_statusText(_stringOf(_quizResult!['new_status']))} · 掌握度 ${_doubleOf(_quizResult!['new_mastery']).toStringAsFixed(1)}%',
                  style: TextStyle(color: colorScheme.onSurfaceVariant),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildEmptyChatState(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(color: colorScheme.primaryContainer, shape: BoxShape.circle),
            child: Icon(Icons.upload_file, size: 40, color: colorScheme.onPrimaryContainer),
          ),
          const SizedBox(height: 24),
          Text("添加来源即可开始使用", style: TextStyle(fontSize: 20, fontWeight: FontWeight.w500, color: colorScheme.onSurface)),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _pickFile,
            icon: const Icon(Icons.add),
            label: const Text("上传来源"),
            style: FilledButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChatBubble(BuildContext context, ChatMessage message) {
    final colorScheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    bool isUser = message.isUser;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.35),
        decoration: BoxDecoration(
          color: isUser ? colorScheme.primaryContainer : colorScheme.surfaceContainer,
          borderRadius: BorderRadius.circular(16),
          border: isUser ? null : Border.all(color: colorScheme.outlineVariant),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (isUser)
              Text(
                message.text,
                style: TextStyle(
                  color: colorScheme.onPrimaryContainer,
                  fontSize: 14,
                  height: 1.5,
                ),
              )
            else
              MarkdownBody(
                data: message.text,
                selectable: true,
                styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
                  p: textTheme.bodyMedium?.copyWith(
                    color: colorScheme.onSurface,
                    fontSize: 14,
                    height: 1.5,
                  ),
                  h1: textTheme.titleLarge?.copyWith(
                    color: colorScheme.onSurface,
                    fontWeight: FontWeight.w700,
                  ),
                  h2: textTheme.titleMedium?.copyWith(
                    color: colorScheme.onSurface,
                    fontWeight: FontWeight.w700,
                  ),
                  h3: textTheme.titleSmall?.copyWith(
                    color: colorScheme.onSurface,
                    fontWeight: FontWeight.w700,
                  ),
                  code: textTheme.bodySmall?.copyWith(
                    color: colorScheme.onSurface,
                    fontFamily: 'monospace',
                  ),
                  codeblockDecoration: BoxDecoration(
                    color: colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  blockquote: textTheme.bodyMedium?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                    height: 1.5,
                  ),
                  blockquoteDecoration: BoxDecoration(
                    color: colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  listBullet: textTheme.bodyMedium?.copyWith(
                    color: colorScheme.onSurface,
                  ),
                  a: textTheme.bodyMedium?.copyWith(
                    color: colorScheme.primary,
                    decoration: TextDecoration.underline,
                  ),
                ),
              ),
            if (message.references.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                '来源: ${message.references.join(', ')}', 
                style: TextStyle(fontSize: 11, color: isUser ? colorScheme.onPrimaryContainer.withOpacity(0.7) : colorScheme.onSurfaceVariant)
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildThinkingBubble(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(border: Border.all(color: colorScheme.outlineVariant), borderRadius: BorderRadius.circular(16)),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: colorScheme.primary)),
            const SizedBox(width: 12),
            Text("正在思考...", style: TextStyle(color: colorScheme.onSurfaceVariant)),
          ],
        ),
      ),
    );
  }

  Widget _buildChatInputArea(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          Container(
            decoration: BoxDecoration(color: colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(28)),
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            child: Row(
              children: [
                const SizedBox(width: 16),
                Expanded(
                  child: TextField(
                    controller: _chatController, 
                    onSubmitted: (_) => _sendMessage(),
                    style: TextStyle(color: colorScheme.onSurface),
                    decoration: InputDecoration(
                      hintText: "上传来源即可开始使用", 
                      hintStyle: TextStyle(color: colorScheme.onSurfaceVariant.withOpacity(0.6), fontSize: 14),
                      border: InputBorder.none, 
                      contentPadding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                  ),
                ),
                Text("${_documents.length} 个来源", style: TextStyle(color: colorScheme.onSurfaceVariant.withOpacity(0.6), fontSize: 12)),
                const SizedBox(width: 12),
                IconButton.filled(
                  onPressed: _sendMessage, 
                  icon: const Icon(Icons.arrow_upward),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          Text("NotebookLM 提供的内容未必准确，因此请仔细核查回答内容。", style: TextStyle(color: colorScheme.onSurfaceVariant.withOpacity(0.6), fontSize: 11)),
        ],
      ),
    );
  }

  Widget _buildRightPanel(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      decoration: BoxDecoration(
        color: colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: colorScheme.outlineVariant),
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text("Studio", style: TextStyle(fontSize: 16, fontWeight: FontWeight.w500, color: colorScheme.onSurface)),
                Icon(Icons.dashboard_customize_outlined, color: colorScheme.onSurfaceVariant, size: 20),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0),
            child: GridView.count(
              crossAxisCount: 3, shrinkWrap: true, physics: const NeverScrollableScrollPhysics(),
              crossAxisSpacing: 8, mainAxisSpacing: 8, childAspectRatio: 1.1,
              children: [
                _buildStudioTool(context, Icons.podcasts, "音频概览", () => _handleStudioAction("audio_overview")),
                _buildStudioTool(context, Icons.smart_display_outlined, "视频概览", () => _handleStudioAction("video_overview")),
                _buildStudioTool(context, Icons.hub_outlined, "思维导图", () => _handleStudioAction("mindmap")),
                _buildStudioTool(context, Icons.summarize_outlined, "报告", () => _handleStudioAction("report")),
                _buildStudioTool(context, Icons.amp_stories_outlined, "闪卡", () => _handleStudioAction("flashcards")),
                _buildStudioTool(context, Icons.quiz_outlined, "测验", () => _handleStudioAction("quiz")),
                _buildStudioTool(context, Icons.insights_outlined, "信息图", () => _handleStudioAction("infographic")),
                _buildStudioTool(context, Icons.co_present_outlined, "演示文稿", () => _handleStudioAction("presentation")),
                _buildStudioTool(context, Icons.table_view_outlined, "数据表格", () => _handleStudioAction("table")),
              ],
            ),
          ),
          if (_isGeneratingStudio)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: [
                  SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: colorScheme.primary)),
                  const SizedBox(width: 8),
                  Expanded(child: Text("正在生成 $_activeStudioTool...", style: TextStyle(color: colorScheme.onSurfaceVariant, fontSize: 12))),
                ],
              ),
            ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              children: [
                _panelTitle(context, '问答设置'),
                DropdownButtonFormField<String>(
                  value: _qaMode,
                  dropdownColor: colorScheme.surfaceContainerHighest,
                  decoration: InputDecoration(
                    isDense: true, filled: true, fillColor: colorScheme.surfaceContainerHighest,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
                  ),
                  items: const ['mix', 'local', 'global', 'hybrid', 'naive', 'bypass']
                      .map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
                  onChanged: (value) { if (value != null) setState(() => _qaMode = value); },
                ),
                CheckboxListTile(
                  dense: true, contentPadding: EdgeInsets.zero,
                  value: _includeReferences, activeColor: colorScheme.primary,
                  onChanged: (value) => setState(() => _includeReferences = value ?? false),
                  title: Text('包含参考文献', style: TextStyle(fontSize: 12, color: colorScheme.onSurface)),
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    Text('每次测验题数', style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant)),
                    const Spacer(),
                    DropdownButton<int>(
                      value: _quizQuestionCount, dropdownColor: colorScheme.surfaceContainerHighest,
                      style: TextStyle(color: colorScheme.onSurface),
                      items: [3, 4, 5, 6, 8, 10].map((e) => DropdownMenuItem(value: e, child: Text('$e'))).toList(),
                      onChanged: (value) { if (value != null) setState(() => _quizQuestionCount = value); },
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                _panelTitle(context, '技能树'),
                if (_isLoadingSkillNodes)
                  Center(child: CircularProgressIndicator(color: colorScheme.primary))
                else if (_skillNodes.isEmpty)
                  Text('暂无技能点', style: TextStyle(color: colorScheme.onSurfaceVariant.withOpacity(0.6)))
                else
                  ..._skillNodes.map((n) => _buildSkillNodeCard(context, n)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _panelTitle(BuildContext context, String title) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(title, style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: Theme.of(context).colorScheme.onSurface)),
    );
  }

  Widget _buildSkillNodeCard(BuildContext context, Map<String, dynamic> node) {
    final colorScheme = Theme.of(context).colorScheme;
    final status = _stringOf(node['status'], fallback: 'locked');
    final mastery = _doubleOf(node['mastery']);
    return Card(
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 8),
      color: colorScheme.surfaceContainer,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10), side: BorderSide(color: colorScheme.outlineVariant)),
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(_stringOf(node['name'], fallback: '未命名技能点'), style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: colorScheme.onSurface)),
            const SizedBox(height: 4),
            Text(_statusText(status), style: TextStyle(fontSize: 11, color: _statusColor(status, colorScheme))),
            const SizedBox(height: 6),
            LinearProgressIndicator(
              value: (mastery.clamp(0, 100)) / 100, minHeight: 5,
              color: colorScheme.primary, backgroundColor: colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(3),
            ),
            const SizedBox(height: 6),
            Text('掌握度 ${mastery.toStringAsFixed(1)}%', style: TextStyle(fontSize: 11, color: colorScheme.onSurfaceVariant)),
            const SizedBox(height: 6),
            Row(
              children: [
                if (status == 'available' || status == 'learning')
                  Expanded(child: FilledButton.tonal(onPressed: () => _startLearning(node), child: const Text('学习', style: TextStyle(fontSize: 11)))),
                if (status == 'available' || status == 'learning') const SizedBox(width: 6),
                if (status == 'learning')
                  Expanded(child: FilledButton.tonal(onPressed: () => _completeLearning(node), child: const Text('完成', style: TextStyle(fontSize: 11)))),
              ],
            ),
            const SizedBox(height: 4),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _isGeneratingQuiz ? null : () => _generateQuizForNode(node),
                style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 10)),
                child: _isGeneratingQuiz && _quizNodeId == _stringOf(node['id'])
                    ? SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: colorScheme.onPrimary))
                    : const Text('出题', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStudioTool(BuildContext context, IconData icon, String label, VoidCallback onTap) {
    final colorScheme = Theme.of(context).colorScheme;
    return Card(
      elevation: 0,
      color: colorScheme.surfaceContainer,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10), side: BorderSide(color: colorScheme.outlineVariant)),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 24, color: colorScheme.onSurfaceVariant),
            const SizedBox(height: 8),
            Text(label, style: TextStyle(color: colorScheme.onSurfaceVariant, fontSize: 11)),
          ],
        ),
      ),
    );
  }
}

class _GraphNodeVm {
  final String id;
  final String label;
  const _GraphNodeVm({required this.id, required this.label});
}

class _GraphEdgeVm {
  final String source;
  final String target;
  final String label;
  const _GraphEdgeVm({required this.source, required this.target, this.label = ''});
}

class _KnowledgeGraphPainter extends CustomPainter {
  final List<_GraphNodeVm> nodes;
  final List<_GraphEdgeVm> edges;
  final Map<String, Offset> positions;
  final ColorScheme colorScheme;

  const _KnowledgeGraphPainter({
    required this.nodes,
    required this.edges,
    required this.positions,
    required this.colorScheme,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final edgePaint = Paint()
      ..color = colorScheme.outlineVariant
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    final nodePaint = Paint()
      ..color = colorScheme.primaryContainer
      ..style = PaintingStyle.fill;

    final borderPaint = Paint()
      ..color = colorScheme.outline
      ..strokeWidth = 1
      ..style = PaintingStyle.stroke;

    for (final edge in edges) {
      final start = positions[edge.source];
      final end = positions[edge.target];
      if (start == null || end == null) continue;
      canvas.drawLine(start, end, edgePaint);
    }

    for (final node in nodes) {
      final point = positions[node.id];
      if (point == null) continue;
      canvas.drawCircle(point, 24, nodePaint);
      canvas.drawCircle(point, 24, borderPaint);

      final textPainter = TextPainter(
        text: TextSpan(
          text: node.label,
          style: TextStyle(
            color: colorScheme.onPrimaryContainer,
            fontSize: 12,
            fontWeight: FontWeight.w500,
          ),
        ),
        maxLines: 2,
        ellipsis: '...',
        textDirection: TextDirection.ltr,
      )..layout(maxWidth: 130);

      textPainter.paint(
        canvas,
        Offset(point.dx - textPainter.width / 2, point.dy + 28),
      );
    }
  }

  @override
  bool shouldRepaint(covariant _KnowledgeGraphPainter oldDelegate) {
    return oldDelegate.nodes != nodes ||
        oldDelegate.edges != edges ||
        oldDelegate.positions != positions ||
        oldDelegate.colorScheme != colorScheme;
  }
}
