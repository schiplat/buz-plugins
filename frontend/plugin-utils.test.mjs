import assert from 'node:assert/strict'
import test from 'node:test'
import { compareVersions, detailPageUrl, formatBuzRequirement, groupPlugins, pluginHeading, selectPluginVersion } from './src/lib/plugin-utils.ts'

const template = (id, version, extra = {}) => ({
  id,
  version,
  file: `plugins/${id}/${version}.yaml`,
  name: `${id} ${version}`,
  engine: 'docker',
  inputs: [],
  content_sha256: version,
  ...extra,
})

test('groups multiple versions into one plugin and chooses the greatest semantic version', () => {
  const templates = [
    template('buz/oss-upload', '1.0.9'),
    template('buz/oss-upload', '1.0.10'),
    template('buz/s3-upload', '1.0.2'),
  ]
  const plugins = groupPlugins(templates)

  assert.equal(plugins.length, 2)
  assert.deepEqual(plugins[0].versions.map(({ version }) => version), ['1.0.10', '1.0.9'])
  assert.equal(plugins[0].latest.version, '1.0.10')
  assert.equal(plugins[0].versions.length, 2)
})

test('compares all three semantic version components numerically', () => {
  assert.ok(compareVersions('1.10.0', '1.9.0') > 0)
  assert.ok(compareVersions('2.0.0', '1.99.99') > 0)
  assert.equal(compareVersions('1.2.3', '1.2.3'), 0)
  assert.throws(() => compareVersions('1.0', '1.0.0'), /Invalid semantic version/)
})

test('selects the full requested version record and maps its static detail URL', () => {
  const plugin = groupPlugins([
    template('buz/oss-upload', '1.0.1', { content_sha256: 'old-hash' }),
    template('buz/oss-upload', '1.0.2', { content_sha256: 'new-hash' }),
  ])[0]

  assert.equal(selectPluginVersion(plugin, '1.0.1').content_sha256, 'old-hash')
  assert.equal(pluginHeading(selectPluginVersion(plugin, '1.0.1'), plugin), 'buz/oss-upload')
  assert.equal(selectPluginVersion(plugin, 'missing').version, '1.0.2')
  assert.equal(detailPageUrl('plugins/buz/oss-upload/1.0.1.yaml'), 'templates/buz/oss-upload/1.0.1.html')

  const singleVersion = groupPlugins([template('buz/one-version', '2.3.4')])[0]
  assert.equal(pluginHeading(singleVersion.latest, singleVersion), 'buz/one-version@2.3.4')
})

test('formats buz requirements for display', () => {
  assert.equal(formatBuzRequirement('>=1.9.0'), '≥ 1.9.0')
  assert.equal(formatBuzRequirement('1.2.0'), '= 1.2.0')
  assert.equal(formatBuzRequirement('<2.0.0'), '<2.0.0')
  assert.equal(formatBuzRequirement('1.2'), '1.2')
})
