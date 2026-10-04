/* Multi-language UI dictionary. Add a language = one entry here + one key
   in LOCALE_NAMES. Template descriptions resolve via the fallback chain
   description_<lang> → description → first available description_*. */

export const LOCALE_NAMES: Record<string, string> = {
  en: 'English',
  zh: '中文',
  // Add UI languages here:
  // ja: '日本語', ko: '한국어', es: 'Español', ...
}

export const I18N: Record<string, Record<string, string | ((...args: unknown[]) => string)>> = {
  en: {
    tagline: 'Extend Buz pipelines with reusable step templates — reference them with uses:',
    search: 'Search by name, id, keyword, author…',
    details: 'Details',
    report: 'Report a template',
    securityNote: 'Security concerns: report privately',
    inputs: 'Inputs',
    usage: 'Usage',
    integrity: 'Integrity',
    name: 'Name',
    type: 'Type',
    required: 'Required',
    masking: 'Masking',
    description: 'Description',
    yes: 'yes',
    no: 'no',
    inputsCount: (n: number) => `${n} input${n === 1 ? '' : 's'}`,
    by: 'by',
    templatesCount: (n: number) => `${n} template${n === 1 ? '' : 's'}`,
    emptySearch: 'No templates match your search.',
    empty: 'No templates installed yet — clone github.com/schiplat/buz-plugins into the Manager step directory to install them.',
    loadFail: 'Failed to load the marketplace',
    incompatible: 'needs a newer Buz',
    sourceRepo: 'Source repository',
    reportHint: 'Report a problem with this template',
    timeout: 'timeout',
    reviewed: 'Reviewed',
    unreviewed: 'Unreviewed',
    official: 'Official',
    community: 'Community',
    all: 'All',
    page: 'Page',
    of: 'of',
    prev: 'Previous',
    next: 'Next',
    reviewedTip: 'Officially reviewed at this content hash — a point-in-time check, not a runtime-safety guarantee',
    unreviewedTip: 'Not in the official review manifest',
    pinHint: 'Review is a point-in-time check of this exact hash — pin with @sha256: to bind a pipeline to it.',
  },
  zh: {
    tagline: 'Buz 流水线的可复用步骤模板——在流水线中通过 uses: 引用',
    search: '按名称、ID、关键词、作者搜索…',
    details: '详情',
    report: '反馈模板问题',
    securityNote: '安全问题请私下举报',
    inputs: '输入参数',
    usage: '用法',
    integrity: '完整性',
    name: '名称',
    type: '类型',
    required: '必填',
    masking: '打码',
    description: '说明',
    yes: '是',
    no: '否',
    inputsCount: (n: number) => `${n} 个输入`,
    by: '作者',
    templatesCount: (n: number) => `${n} 个模板`,
    emptySearch: '没有匹配的模板。',
    empty: '尚未安装模板——将 github.com/schiplat/buz-plugins 克隆到 Manager 的步骤目录即可。',
    loadFail: '插件市场加载失败',
    incompatible: '需要更新版本的 Buz',
    sourceRepo: '源仓库',
    reportHint: '反馈此模板的问题',
    timeout: '超时',
    reviewed: '已审核',
    unreviewed: '未审核',
    official: '官方',
    community: '社区',
    all: '全部',
    page: '页',
    of: '/',
    prev: '上一页',
    next: '下一页',
    reviewedTip: '官方已审核该内容哈希——时间点检查，不构成运行时安全保证',
    unreviewedTip: '不在官方审核清单中',
    pinHint: '审核是对该内容哈希的时间点检查——在流水线中用 @sha256: 钉版可绑定到此内容。',
  },
}

export function detectLanguage(supported: string[], fallback = 'en'): string {
  const saved = localStorage.getItem('buz-marketplace-lang')
  if (saved && supported.includes(saved)) return saved
  for (const candidate of navigator.languages || [navigator.language || fallback]) {
    const code = String(candidate).toLowerCase()
    if (supported.includes(code)) return code
    const base = code.split('-')[0]
    if (supported.includes(base)) return base
  }
  return fallback
}
