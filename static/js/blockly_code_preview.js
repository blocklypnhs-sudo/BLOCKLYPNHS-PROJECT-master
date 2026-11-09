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
        .blockly-toolbox-toggle {
            display: none;
        }
        @media (max-width: 768px) {
            .blockly-code-layout {
                position: relative;
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
            .blockly-toolbox-toggle {
                position: absolute;
                top: 8px;
                left: 8px;
                z-index: 50;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 30px;
                height: 30px;
                padding: 0;
                border: 1px solid rgba(255,255,255,0.28);
                border-radius: 9px;
                background: #12604a;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                color: #fff;
                cursor: pointer;
                font-size: 0.75rem;
                touch-action: manipulation;
                transition: left 180ms ease;
            }
            .blockly-toolbox-toggle:focus-visible {
                outline: 2px solid #e8b93c;
                outline-offset: 2px;
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

        const toolbox = typeof workspace.getToolbox === 'function'
            ? workspace.getToolbox()
            : null;
        if (toolbox && typeof toolbox.setVisible === 'function') {
            const existingToggle = layout.querySelector('.blockly-toolbox-toggle');
            if (existingToggle) existingToggle.remove();

            const toolboxToggle = document.createElement('button');
            toolboxToggle.className = 'blockly-toolbox-toggle';
            toolboxToggle.type = 'button';
            toolboxToggle.setAttribute('aria-expanded', 'true');
            toolboxToggle.setAttribute('aria-label', 'Close blocks toolbox');
            toolboxToggle.title = 'Close blocks toolbox';
            toolboxToggle.innerHTML = '<i class="fas fa-chevron-left" aria-hidden="true"></i>';

            let toolboxVisible = true;
            const getFlyoutElement = function () {
                const flyout = typeof toolbox.getFlyout === 'function'
                    ? toolbox.getFlyout()
                    : null;
                const flyoutRoot = flyout && typeof flyout.getSvgRoot === 'function'
                    ? flyout.getSvgRoot()
                    : null;
                if (flyoutRoot) {
                    const flyoutRect = flyoutRoot.getBoundingClientRect();
                    if (flyoutRect.width > 0 && flyoutRect.height > 0) return flyoutRoot;
                }

                return Array.from(blocklyElement.querySelectorAll('.blocklyFlyout'))
                    .find(function (element) {
                        const style = window.getComputedStyle(element);
                        const rect = element.getBoundingClientRect();
                        return style.display !== 'none' &&
                            style.visibility !== 'hidden' &&
                            rect.width > 0 &&
                            rect.height > 0;
                    }) || null;
            };
            const positionToggle = function () {
                if (!toolboxVisible) {
                    toolboxToggle.style.left = '0px';
                    return;
                }
                const toolboxElement = blocklyElement.querySelector('.blocklyToolboxDiv');
                if (!toolboxElement) return;
                const layoutRect = layout.getBoundingClientRect();
                const toolboxRect = toolboxElement.getBoundingClientRect();
                let edgeRight = toolboxRect.right;
                const flyoutElement = getFlyoutElement();
                if (flyoutElement) {
                    const flyoutStyle = window.getComputedStyle(flyoutElement);
                    if (flyoutStyle.display !== 'none' && flyoutStyle.visibility !== 'hidden') {
                        const flyoutBackground = flyoutElement.querySelector('.blocklyFlyoutBackground');
                        const flyoutElementRect = flyoutElement.getBoundingClientRect();
                        const flyoutBackgroundRect = flyoutBackground
                            ? flyoutBackground.getBoundingClientRect()
                            : null;
                        const flyoutRect = flyoutBackgroundRect &&
                            flyoutBackgroundRect.width > 0 &&
                            (
                                flyoutBackgroundRect.width > flyoutElementRect.width ||
                                flyoutBackgroundRect.right > flyoutElementRect.right
                            )
                            ? flyoutBackgroundRect
                            : flyoutElementRect;
                        if (
                            flyoutRect.width > 0 &&
                            flyoutRect.right > toolboxRect.right &&
                            flyoutRect.left < layoutRect.right &&
                            flyoutRect.right > layoutRect.left
                        ) {
                            edgeRight = Math.max(edgeRight, flyoutRect.right);
                        }
                    }
                }
                if (edgeRight > layoutRect.left) {
                    toolboxToggle.style.left = (edgeRight - layoutRect.left + 4) + 'px';
                }
            };
            let positionTimers = [];
            const scheduleTogglePosition = function (followFlyout = false) {
                window.requestAnimationFrame(positionToggle);
                positionTimers.forEach(function (timer) {
                    window.clearTimeout(timer);
                });
                positionTimers = [];
                if (!toolboxVisible || !window.matchMedia('(max-width: 768px)').matches) return;
                const delays = followFlyout ? [50, 150, 300] : [100, 250, 400];
                positionTimers = delays.map(function (delay) {
                    return window.setTimeout(function () {
                        window.requestAnimationFrame(positionToggle);
                    }, delay);
                });
            };

            toolboxToggle.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();
                toolboxVisible = !toolboxVisible;
                if (!toolboxVisible && typeof toolbox.clearSelection === 'function') {
                    toolbox.clearSelection();
                }
                toolbox.setVisible(toolboxVisible);
                toolboxToggle.setAttribute('aria-expanded', String(toolboxVisible));
                toolboxToggle.setAttribute(
                    'aria-label',
                    toolboxVisible ? 'Close blocks toolbox' : 'Open blocks toolbox'
                );
                toolboxToggle.title = toolboxVisible
                    ? 'Close blocks toolbox'
                    : 'Open blocks toolbox';
                toolboxToggle.innerHTML = '<i class="fas fa-chevron-' +
                    (toolboxVisible ? 'left' : 'right') + '" aria-hidden="true"></i>';
                if (toolboxVisible) {
                    window.requestAnimationFrame(function () {
                        positionToggle();
                        if (window.Blockly && typeof Blockly.svgResize === 'function') {
                            Blockly.svgResize(workspace);
                        }
                    });
                } else {
                    positionToggle();
                    if (window.Blockly && typeof Blockly.svgResize === 'function') {
                        Blockly.svgResize(workspace);
                    }
                }
            });
            layout.appendChild(toolboxToggle);
            scheduleTogglePosition();
            if ('ResizeObserver' in window) {
                const resizeObserver = new ResizeObserver(scheduleTogglePosition);
                resizeObserver.observe(layout);
                resizeObserver.observe(blocklyElement);
                const flyoutElement = getFlyoutElement();
                if (flyoutElement) resizeObserver.observe(flyoutElement);
            }
            if ('MutationObserver' in window) {
                const flyoutObserver = new MutationObserver(scheduleTogglePosition);
                const flyoutElement = getFlyoutElement();
                flyoutObserver.observe(flyoutElement || blocklyElement, {
                    attributes: true,
                    attributeFilter: ['class', 'style', 'transform'],
                    childList: true,
                    subtree: true
                });
            }
            workspace.addChangeListener(function (event) {
                if (event.isUiEvent) scheduleTogglePosition(true);
            });
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
