import { describe, it, expect } from 'vitest';
import { injectInspector, buildInspectorScript } from './inspector';

describe('inspector', () => {
  describe('buildInspectorScript', () => {
    it('returns a script tag', () => {
      const script = buildInspectorScript();
      expect(script).toContain('<script>');
      expect(script).toContain('</script>');
    });

    it('includes inspect mode handling', () => {
      const script = buildInspectorScript();
      expect(script).toContain('set_inspect_mode');
      expect(script).toContain('element_selected');
      expect(script).toContain('apply_html');
      expect(script).toContain('undo');
    });

    it('includes hover and selected CSS classes', () => {
      const script = buildInspectorScript();
      expect(script).toContain('__arc-hover');
      expect(script).toContain('__arc-selected');
    });
  });

  describe('injectInspector', () => {
    it('injects before </body> when present', () => {
      const html = '<html><body><p>hello</p></body></html>';
      const result = injectInspector(html);
      expect(result).toContain('<script>');
      expect(result.indexOf('<script>')).toBeLessThan(result.indexOf('</body>'));
    });

    it('appends at end when no </body>', () => {
      const html = '<p>hello</p>';
      const result = injectInspector(html);
      expect(result).toContain('<p>hello</p>');
      expect(result).toContain('<script>');
    });

    it('preserves original html content', () => {
      const html = '<div class="card"><h2>Title</h2></div>';
      const result = injectInspector(html);
      expect(result).toContain('<div class="card"><h2>Title</h2></div>');
    });
  });
});
