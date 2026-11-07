(function () {
    const styles = `
        .blockly-code-layout {
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
            width: 100%;
            height: 340px;
            min-height: 260px;
            overflow: hidden;
            background: #fff;
        }
        .blockly-code-layout > [id^="blocklyDiv"] {
            width: 100% !important;
            height: 100% !important;
            min-height: 0 !important;
            max-height: none !important;
            background: #fefefb;
        }
        .workspace-wrapper.has-code-preview {
            height: 400px;
            min-height: 320px;
            max-height: 540px;
        }
        .workspace-wrapper.has-code-preview > .blockly-code-layout {
            height: 100%;
            min-height: 0;
        }
        .blockly-code-preview {
            display: flex;
            flex-direction: column;
            min-width: 0;
            min-height: 0;
            overflow: hidden;
            border-left: 1px solid #e0ebe4;
            background: #fff;
        }
        .blockly-code-preview-header {
            display: flex;
            flex-shrink: 0;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
            min-height: 42px;
            padding: 8px 12px;
            border-bottom: 1px solid #e5e7eb;
            color: #10382c;
            font: 700 12px/1.4 Inter, system-ui, sans-serif;
        }
        .blockly-code-preview-language {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .blockly-code-preview-badge {
            flex-shrink: 0;
            padding: 3px 8px;
            border-radius: 20px;
            background: #e3f4ec;
            color: #12604a;
            font-size: 9px;
            letter-spacing: .5px;
        }
        .blockly-code-preview pre {
            flex: 1;
            min-width: 0;
            min-height: 0;
            overflow: auto;
            margin: 0;
            padding: 14px;
            background: #fff;
            color: #263238;
            font: 12px/1.65 "SFMono-Regular", Consolas, "Liberation Mono", monospace;
            text-align: left;
            white-space: pre;
            tab-size: 4;
        }
        .blockly-code-preview code {
            font: inherit;
        }
        @media (max-width: 768px) {
            .blockly-code-layout {
                grid-template-columns: minmax(0, 1fr);
                height: auto;
                min-height: 0;
                overflow: visible;
            }
            .blockly-code-layout > [id^="blocklyDiv"] {
                height: min(45vh, 340px) !important;
                min-height: 240px !important;
            }
            .blockly-code-preview {
                height: 220px;
                border-top: 1px solid #e0ebe4;
                border-left: 0;
            }
            .workspace-wrapper.has-code-preview {
                height: auto !important;
                min-height: 0 !important;
                max-height: none !important;
                overflow: visible !important;
            }
        }
    `;

    const styleElement = document.createElement('style');
    styleElement.textContent = styles;
    document.head.appendChild(styleElement);

    window.attachBlocklyCodePreview = function (workspace, blocklyElementId, generateCode, language) {
        const blocklyElement = document.getElementById(blocklyElementId);
        if (!workspace || !blocklyElement || typeof generateCode !== 'function') {
            throw new Error('Cannot attach the generated-code preview to this Blockly workspace.');
        }

        let layout = blocklyElement.parentElement;
        if (!layout.classList.contains('blockly-code-layout')) {
            layout = document.createElement('div');
            layout.className = 'blockly-code-layout';
            blocklyElement.parentNode.insertBefore(layout, blocklyElement);
            layout.appendChild(blocklyElement);
        }

        const workspaceWrapper = layout.parentElement;
        if (workspaceWrapper.classList.contains('workspace-wrapper')) {
            workspaceWrapper.classList.add('has-code-preview');
        }

        let preview = layout.querySelector('.blockly-code-preview');
        if (!preview) {
            preview = document.createElement('section');
            preview.className = 'blockly-code-preview';
            preview.setAttribute('aria-label', 'Generated code preview');
            preview.setAttribute('aria-readonly', 'true');

            const header = document.createElement('div');
            header.className = 'blockly-code-preview-header';

            const title = document.createElement('span');
            title.className = 'blockly-code-preview-language';

            const badge = document.createElement('span');
            badge.className = 'blockly-code-preview-badge';
            badge.textContent = 'VIEW ONLY';

            const codeContainer = document.createElement('pre');
            codeContainer.setAttribute('tabindex', '0');
            codeContainer.setAttribute('aria-label', 'Generated code, read only');
            const code = document.createElement('code');
            codeContainer.appendChild(code);

            header.append(title, badge);
            preview.append(header, codeContainer);
            layout.appendChild(preview);
        }

        preview.querySelector('.blockly-code-preview-language').textContent =
            (language || 'Generated') + ' code';
        const codeElement = preview.querySelector('code');
        let renderScheduled = false;

        const updatePreview = function () {
            renderScheduled = false;
            try {
                const code = generateCode();
                codeElement.textContent = code && code.trim()
                    ? code
                    : 'Add blocks to see the generated code.';
            } catch (error) {
                console.error('Unable to generate Blockly code preview.', error);
                codeElement.textContent = 'Unable to generate code preview: ' + error.message;
            }
        };

        workspace.addChangeListener(function (event) {
            if (event.isUiEvent || renderScheduled) return;
            renderScheduled = true;
            window.requestAnimationFrame(updatePreview);
        });

        if (window.Blockly && typeof Blockly.svgResize === 'function') {
            window.requestAnimationFrame(function () {
                Blockly.svgResize(workspace);
            });
        }
        updatePreview();
    };
})();
