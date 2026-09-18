/**
 * SchoolSM Digital Tools AI Assistant
 * Powered by Google Gemini 3.8 Flash (Low / Medium / High Thinking Levels)
 */

const ToolAiAssistant = (function () {
    // Get CSRF Token
    function getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
            document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1] || '';
    }

    // Get active thinking level
    function getThinkingLevel() {
        return localStorage.getItem('schoolsm_ai_thinking_level') || 'medium';
    }

    // Simple markdown renderer for modal display
    function renderMarkdown(md) {
        if (!md) return '';
        let html = md
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            // Headers
            .replace(/^### (.*$)/gim, '<h6 class="fw-bold text-primary mt-3 mb-2">$1</h6>')
            .replace(/^## (.*$)/gim, '<h5 class="fw-bold text-dark mt-3 mb-2">$1</h5>')
            .replace(/^# (.*$)/gim, '<h4 class="fw-bold text-dark mt-3 mb-2">$1</h4>')
            // Bold and Italic
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            // Lists
            .replace(/^\s*[-*]\s+(.*)$/gim, '<li class="ms-3 mb-1">$1</li>')
            .replace(/(<li.*<\/li>)/s, '<ul class="ps-2 my-2">$1</ul>')
            // Code block
            .replace(/```([\s\S]*?)```/g, '<pre class="bg-dark text-light p-3 rounded-3 small overflow-x-auto"><code>$1</code></pre>')
            .replace(/`([^`]+)`/g, '<code class="bg-light text-danger px-1.5 py-0.5 rounded small">$1</code>')
            // Line breaks
            .replace(/\n/g, '<br>');

        return html;
    }

    // Ensure modal container exists in DOM
    function ensureModalContainer() {
        let modalEl = document.getElementById('toolAiResultModal');
        if (!modalEl) {
            const modalHtml = `
                <div class="modal fade" id="toolAiResultModal" tabindex="-1" aria-labelledby="toolAiResultModalLabel" aria-hidden="true">
                    <div class="modal-dialog modal-dialog-centered modal-lg modal-dialog-scrollable">
                        <div class="modal-content border-0 shadow-lg rounded-4">
                            <div class="modal-header border-bottom py-3 px-4" style="background: linear-gradient(135deg, #1e3c72, #2a5298); color: white;">
                                <div class="d-flex align-items-center gap-2">
                                    <div class="rounded-circle d-flex align-items-center justify-content-center" style="width: 34px; height: 34px; background: rgba(255,255,255,0.2);">
                                        <i class="fa-solid fa-wand-magic-sparkles"></i>
                                    </div>
                                    <div>
                                        <h6 class="modal-title fw-bold mb-0" id="toolAiResultModalLabel">✨ លទ្ធផលពី Gemini 3.8 Flash AI</h6>
                                        <small class="text-white-50" id="toolAiProviderBadge" style="font-size: 0.72rem;">Gemini 3.8 Flash • SchoolSM</small>
                                    </div>
                                </div>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body p-4" id="toolAiModalBody">
                                <div id="toolAiRenderedContent" class="line-height-relaxed" style="font-size: 0.95rem;"></div>
                            </div>
                            <div class="modal-footer border-top px-4 py-3 d-flex justify-content-between">
                                <button type="button" class="btn btn-outline-secondary rounded-pill px-3" data-bs-dismiss="modal">
                                    <i class="fa-solid fa-xmark me-1"></i> បិទ
                                </button>
                                <div class="d-flex gap-2">
                                    <button type="button" class="btn btn-outline-primary rounded-pill px-3" id="toolAiCopyBtn">
                                        <i class="fa-regular fa-copy me-1"></i> ចម្លង (Copy)
                                    </button>
                                    <button type="button" class="btn btn-success rounded-pill px-3 d-none" id="toolAiApplyBtn">
                                        <i class="fa-solid fa-check me-1"></i> ជំនួសក្នុងផ្ទាំង (Apply to Workspace)
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            modalEl = document.getElementById('toolAiResultModal');
        }
        return modalEl;
    }

    /**
     * Executes an AI tool action and displays result modal or invokes callback
     */
    function run(params) {
        const {
            tool,
            action,
            actionTitle = 'លទ្ធផល AI',
            content = '',
            options = {},
            thinkingLevel = null,
            onSuccess = null,
            onApply = null,
            autoApply = false
        } = params;

        if (!content && action !== 'quiz_wheel') {
            if (typeof Swal !== 'undefined') {
                Swal.fire({
                    icon: 'warning',
                    title: 'សូមបញ្ចូលខ្លឹមសារ!',
                    text: 'សូមវាយបញ្ចូល ឬបិទភ្ជាប់ (Paste) អត្ថបទក្នុងផ្ទាំងជាមុនសិន មុននឹងប្រើប្រាស់ AI។',
                    confirmButtonColor: '#1e3c72',
                    confirmButtonText: 'យល់ព្រម'
                });
            } else {
                alert('សូមបញ្ចូល ឬជ្រើសរើសខ្លឹមសារជាមុនសិន!');
            }
            return;
        }

        const activeThinkingLevel = thinkingLevel || getThinkingLevel();
        const levelLabels = {
            'low': '⚡ Low (លឿន)',
            'medium': '⚖️ Medium (លំនឹង)',
            'high': '🧠 High (វិភាគស៊ីជម្រៅ)'
        };
        const levelBadge = levelLabels[activeThinkingLevel] || 'Gemini 3.8 Flash';

        // Show Loading
        if (typeof Swal !== 'undefined') {
            Swal.fire({
                title: 'កំពុងដំណើរការ...',
                html: `
                    <div class="py-2 text-center">
                        <div class="spinner-border text-primary mb-3" style="width: 3rem; height: 3rem;" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <div class="fw-bold text-dark fs-6 mb-1">✨ Gemini 3.8 Flash AI Agent</div>
                        <div class="small text-muted mb-2">កំពុងវិភាគ និងដំណើរការ៖ <span class="badge bg-primary bg-opacity-10 text-primary">${actionTitle}</span></div>
                        <div class="small text-muted" style="font-size: 0.75rem;">កម្រិតគិត៖ <strong>${levelBadge}</strong></div>
                    </div>
                `,
                showConfirmButton: false,
                allowOutsideClick: false,
                allowEscapeKey: false
            });
        }

        // Send API Request
        fetch('/tools/api/ai-assist/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                tool: tool,
                action: action,
                content: content,
                options: options,
                thinking_level: activeThinkingLevel
            })
        })
        .then(res => res.json())
        .then(data => {
            if (typeof Swal !== 'undefined') {
                Swal.close();
            }

            if (data.status === 'success') {
                const resultText = data.result || '';

                // If autoApply is requested and onApply exists, apply directly
                if (autoApply && typeof onApply === 'function') {
                    onApply(resultText);
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            icon: 'success',
                            title: 'ជោគជ័យ!',
                            text: 'AI បានកែសម្រួល និងបញ្ចូលក្នុងផ្ទាំងការងាររបស់អ្នករួចរាល់។',
                            timer: 2000,
                            showConfirmButton: false
                        });
                    }
                    return;
                }

                if (typeof onSuccess === 'function') {
                    onSuccess(resultText, data);
                    return;
                }

                // Show default result modal
                showResultModal({
                    title: `✨ ${actionTitle}`,
                    provider: `${data.provider || 'Gemini 3.8 Flash'} (${levelBadge})`,
                    resultText: resultText,
                    onApply: onApply
                });
            } else {
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        icon: 'error',
                        title: 'មានបញ្ហាក្នុងការដំណើរការ',
                        text: data.message || 'សូមព្យាយាមម្តងទៀត។',
                        confirmButtonColor: '#1e3c72'
                    });
                } else {
                    alert('Error: ' + (data.message || 'Unknown error'));
                }
            }
        })
        .catch(err => {
            if (typeof Swal !== 'undefined') {
                Swal.close();
                Swal.fire({
                    icon: 'error',
                    title: 'បរាជ័យក្នុងការតភ្ជាប់',
                    text: 'មិនអាចតភ្ជាប់ទៅកាន់ម៉ាស៊ីនបម្រើ AI ឡើយ។ សូមពិនិត្យមើលអ៊ីនធឺណិត និងសាកល្បងម្តងទៀត។',
                    confirmButtonColor: '#1e3c72'
                });
            } else {
                alert('Connection error');
            }
        });
    }

    function showResultModal({ title, provider, resultText, onApply }) {
        const modalEl = ensureModalContainer();
        const titleEl = document.getElementById('toolAiResultModalLabel');
        const badgeEl = document.getElementById('toolAiProviderBadge');
        const contentEl = document.getElementById('toolAiRenderedContent');
        const copyBtn = document.getElementById('toolAiCopyBtn');
        const applyBtn = document.getElementById('toolAiApplyBtn');

        if (titleEl) titleEl.textContent = title;
        if (badgeEl) badgeEl.textContent = provider;
        if (contentEl) contentEl.innerHTML = renderMarkdown(resultText);

        // Copy button handler
        if (copyBtn) {
            copyBtn.onclick = function () {
                navigator.clipboard.writeText(resultText).then(() => {
                    const originalHtml = copyBtn.innerHTML;
                    copyBtn.innerHTML = '<i class="fa-solid fa-check me-1"></i> បានចម្លង!';
                    copyBtn.classList.remove('btn-outline-primary');
                    copyBtn.classList.add('btn-primary');
                    setTimeout(() => {
                        copyBtn.innerHTML = originalHtml;
                        copyBtn.classList.remove('btn-primary');
                        copyBtn.classList.add('btn-outline-primary');
                    }, 2000);
                }).catch(() => {
                    alert('មិនអាចចម្លងបានទេ សូមជ្រើសរើស Text រួច Copy ដោយផ្ទាល់។');
                });
            };
        }

        // Apply button handler
        if (applyBtn) {
            if (typeof onApply === 'function') {
                applyBtn.classList.remove('d-none');
                applyBtn.onclick = function () {
                    onApply(resultText);
                    const bsModal = bootstrap.Modal.getInstance(modalEl);
                    if (bsModal) bsModal.hide();
                    if (typeof Swal !== 'undefined') {
                        const Toast = Swal.mixin({
                            toast: true,
                            position: 'top-end',
                            showConfirmButton: false,
                            timer: 2500,
                            timerProgressBar: true
                        });
                        Toast.fire({
                            icon: 'success',
                            title: 'បានជំនួសអត្ថបទក្នុងផ្ទាំងរួចរាល់'
                        });
                    }
                };
            } else {
                applyBtn.classList.add('d-none');
            }
        }

        // Show Bootstrap Modal
        const bsModal = new bootstrap.Modal(modalEl);
        bsModal.show();
    }

    return {
        run: run,
        showResultModal: showResultModal
    };
})();

// Export globally
window.ToolAiAssistant = ToolAiAssistant;
