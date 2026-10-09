import type { StepTemplate } from '../types'

const VERSION_PATTERN = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/

export interface StepPlugin {
  id: string
  versions: StepTemplate[]
  latest: StepTemplate
}

export function compareVersions(a: string, b: string): number {
  const aMatch = VERSION_PATTERN.exec(a)
  const bMatch = VERSION_PATTERN.exec(b)
  if (!aMatch || !bMatch) {
    throw new Error(`Invalid semantic version: ${!aMatch ? a : b}`)
  }

  for (let index = 1; index <= 3; index += 1) {
    const difference = Number(aMatch[index]) - Number(bMatch[index])
    if (difference !== 0) return difference
  }
  return 0
}

export function groupPlugins(templates: StepTemplate[]): StepPlugin[] {
  const groups = new Map<string, StepTemplate[]>()
  for (const template of templates) {
    const versions = groups.get(template.id) || []
    versions.push(template)
    groups.set(template.id, versions)
  }

  return [...groups.entries()]
    .map(([id, versions]) => {
      versions.sort((a, b) => compareVersions(b.version, a.version))
      return { id, versions, latest: versions[0] }
    })
    .sort((a, b) => a.id.localeCompare(b.id))
}

export function pluginHeading(template: StepTemplate, plugin: StepPlugin | null): string {
  return plugin && plugin.versions.length > 1
    ? template.id
    : `${template.id}@${template.version}`
}

export function selectPluginVersion(plugin: StepPlugin, version: string): StepTemplate {
  return plugin.versions.find((template) => template.version === version) || plugin.latest
}

export function detailPageUrl(file: string): string {
  const path = file.replaceAll('\\', '/').replace(/^plugins\//, '')
  return `templates/${path.replace(/\.(yaml|yml)$/i, '.html')}`
}
