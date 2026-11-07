(function () {
    const workspaceKeysById = {
        blocklyDiv: 'guided',
        blocklyDiv2: 'independent',
        blocklyDiv3: 'assessment'
    };

    window.clearModuleStepWorkspace = function (step, workspaces, generatedCode) {
        const section = document.querySelector(`.section[data-step="${step}"]`);
        if (!section) return;

        section.querySelectorAll('[id^="blocklyDiv"]').forEach(function (workspaceElement) {
            const workspaceKey = workspaceKeysById[workspaceElement.id];
            const workspace = workspaceKey && workspaces[workspaceKey];
            if (workspace) {
                workspace.clear();
            }
            if (workspaceKey && generatedCode) {
                delete generatedCode[workspaceKey];
            }
        });

        section.querySelectorAll('.output-text').forEach(function (output) {
            output.textContent = 'Run your code to see output';
            output.className = 'output-text';
        });
    };
})();
