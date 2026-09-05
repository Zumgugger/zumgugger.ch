/**
 * Admin functionality - Edit mode and toolbar
 */

(function() {
    'use strict';
    
    // State
    let eyeModeActive = false;
    let saveTimeout = null;
    let draggedModule = null;
    let dragPlaceholder = null;
    
    // Elements
    const toolbar = document.getElementById('admin-toolbar');
    const eyeToggle = document.getElementById('eye-toggle');
    const undoBtn = document.getElementById('undo-btn');
    const menuToggle = document.getElementById('menu-toggle');
    const adminDropdown = document.getElementById('admin-dropdown');
    
    // ========================================
    // Eye Mode (Section Management)
    // ========================================
    
    // Check if we should auto-activate eye mode (e.g., after toggle)
    function checkAutoActivateEyeMode() {
        const url = new URL(window.location.href);
        if (url.searchParams.get('eyemode') === '1') {
            // Remove the parameter from URL without reload
            url.searchParams.delete('eyemode');
            window.history.replaceState({}, '', url.toString());
            return true;
        }
        return false;
    }
    
    if (eyeToggle) {
        // Auto-activate eye mode if returning from toggle
        if (checkAutoActivateEyeMode()) {
            eyeModeActive = true;
            document.body.classList.add('eye-mode-active');
            eyeToggle.classList.add('active');
            // Defer initialization to ensure DOM is fully ready
            setTimeout(function() {
                initEyeMode();
            }, 100);
        }
        
        eyeToggle.addEventListener('click', function() {
            eyeModeActive = !eyeModeActive;
            document.body.classList.toggle('eye-mode-active', eyeModeActive);
            eyeToggle.classList.toggle('active', eyeModeActive);
            
            if (eyeModeActive) {
                initEyeMode();
            } else {
                cleanupEyeMode();
            }
        });
    }
    
    // ========================================
    // Eye Mode Initialization
    // ========================================
    
    function initEyeMode() {
        // Show disabled modules
        document.querySelectorAll('.module.module-disabled').forEach(function(module) {
            module.style.display = 'block';
        });
        
        // Initialize drag and drop and controls for all modules
        initModuleDragAndDrop();
    }
    
    function cleanupEyeMode() {
        // Hide disabled modules
        document.querySelectorAll('.module.module-disabled').forEach(function(module) {
            module.style.display = 'none';
        });
        
        // Cleanup drag and drop
        cleanupDragAndDrop();
    }
    
    // ========================================
    // Module Drag and Drop (Eye Mode)
    // ========================================
    
    function initModuleDragAndDrop() {
        const modules = document.querySelectorAll('.module[data-module]');
        const main = document.querySelector('.site-main');
        
        // Add dragover to main container to allow drops anywhere
        if (main) {
            main.addEventListener('dragover', function(e) {
                if (!eyeModeActive || !draggedModule) return;
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
            });
            
            main.addEventListener('drop', function(e) {
                if (!eyeModeActive || !draggedModule) return;
                // If drop happened on main but not on a module, find nearest module
                handleMainDrop(e);
            });
        }
        
        modules.forEach(function(module) {
            const moduleName = module.dataset.module;
            const isDisabled = module.classList.contains('module-disabled');
            // Core modules cannot be toggled off - only hero, about, contact, footer
            const isCore = ['hero', 'about', 'contact', 'footer'].includes(moduleName);
            
            // Add controls if not present
            let controls = module.querySelector('.module-controls');
            if (!controls) {
                controls = document.createElement('div');
                controls.className = 'module-controls';
                
                // Build control buttons
                let controlsHTML = '';
                
                // Toggle visibility button (only for non-core modules)
                if (!isCore) {
                    const toggleIcon = isDisabled ? 
                        // Eye-off icon (module is disabled)
                        `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                            <line x1="1" y1="1" x2="23" y2="23"></line>
                        </svg>` :
                        // Eye icon (module is enabled)
                        `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                            <circle cx="12" cy="12" r="3"></circle>
                        </svg>`;
                    
                    controlsHTML += `
                        <button class="module-toggle-btn module-visibility-toggle" 
                                data-module="${moduleName}" 
                                data-enabled="${!isDisabled}"
                                title="${isDisabled ? 'Modul aktivieren' : 'Modul deaktivieren'}">
                            ${toggleIcon}
                        </button>
                    `;
                }
                
                // Drag handle
                controlsHTML += `
                    <button class="module-toggle-btn module-drag-handle" title="Ziehen zum Sortieren">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="3" y1="9" x2="21" y2="9"></line>
                            <line x1="3" y1="15" x2="21" y2="15"></line>
                        </svg>
                    </button>
                `;
                
                controls.innerHTML = controlsHTML;
                module.appendChild(controls);
                
                // Add click handler for visibility toggle
                const toggleBtn = controls.querySelector('.module-visibility-toggle');
                if (toggleBtn) {
                    toggleBtn.addEventListener('click', function(e) {
                        e.stopPropagation();
                        const mod = this.dataset.module;
                        const currentlyEnabled = this.dataset.enabled === 'true';
                        toggleModuleVisibility(mod, !currentlyEnabled);
                    });
                }
            }
            
            // Make module draggable
            module.setAttribute('draggable', 'true');
            
            // Drag events
            module.addEventListener('dragstart', handleDragStart);
            module.addEventListener('dragend', handleDragEnd);
            module.addEventListener('dragover', handleDragOver);
            module.addEventListener('dragenter', handleDragEnter);
            module.addEventListener('dragleave', handleDragLeave);
            module.addEventListener('drop', handleDrop);
        });
    }
    
    function cleanupDragAndDrop() {
        const modules = document.querySelectorAll('.module[data-module]');
        
        modules.forEach(function(module) {
            module.removeAttribute('draggable');
            module.removeEventListener('dragstart', handleDragStart);
            module.removeEventListener('dragend', handleDragEnd);
            module.removeEventListener('dragover', handleDragOver);
            module.removeEventListener('dragenter', handleDragEnter);
            module.removeEventListener('dragleave', handleDragLeave);
            module.removeEventListener('drop', handleDrop);
            
            // Remove controls
            const controls = module.querySelector('.module-controls');
            if (controls) {
                controls.remove();
            }
        });
        
        if (dragPlaceholder && dragPlaceholder.parentNode) {
            dragPlaceholder.parentNode.removeChild(dragPlaceholder);
        }
        dragPlaceholder = null;
        draggedModule = null;
    }
    
    // ========================================
    // Module Visibility Toggle
    // ========================================
    
    async function toggleModuleVisibility(moduleName, enable) {
        showSaving();
        
        try {
            const response = await fetch('/api/admin/module/toggle', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
                body: JSON.stringify({ module: moduleName, enabled: enable }),
            });
            
            if (response.ok) {
                showSaveSuccess();
                // Reload page with eye mode flag to stay in eye mode
                setTimeout(() => {
                    const url = new URL(window.location.href);
                    url.searchParams.set('eyemode', '1');
                    window.location.href = url.toString();
                }, 500);
            } else if (response.status === 401) {
                showSessionExpiredModal();
            } else {
                const data = await response.json();
                showSaveError(data.message || 'Änderung fehlgeschlagen');
            }
        } catch (error) {
            showSaveError('Netzwerkfehler');
        }
    }
    
    function handleDragStart(e) {
        if (!eyeModeActive) return;
        
        draggedModule = this;
        this.classList.add('module-dragging');
        
        // Create placeholder
        dragPlaceholder = document.createElement('div');
        dragPlaceholder.className = 'module-placeholder';
        dragPlaceholder.style.height = this.offsetHeight + 'px';
        
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', this.dataset.module);
        
        // Delay hiding to allow drag image
        setTimeout(() => {
            this.style.opacity = '0.4';
        }, 0);
    }
    
    function handleDragEnd(e) {
        if (!eyeModeActive) return;
        
        this.classList.remove('module-dragging');
        this.style.opacity = '1';
        
        // Remove placeholder if it still exists (drag was cancelled)
        if (dragPlaceholder && dragPlaceholder.parentNode) {
            dragPlaceholder.parentNode.removeChild(dragPlaceholder);
            dragPlaceholder = null;
        }
        
        // Remove drag-over from all modules
        document.querySelectorAll('.module.drag-over').forEach(function(m) {
            m.classList.remove('drag-over');
        });
        
        draggedModule = null;
    }
    
    function handleDragOver(e) {
        if (!eyeModeActive || !draggedModule) return;
        
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        
        const targetModule = this;
        if (targetModule === draggedModule) return;
        
        const rect = targetModule.getBoundingClientRect();
        const midY = rect.top + rect.height / 2;
        
        // Determine if we're above or below the middle
        if (e.clientY < midY) {
            targetModule.parentNode.insertBefore(dragPlaceholder, targetModule);
        } else {
            targetModule.parentNode.insertBefore(dragPlaceholder, targetModule.nextSibling);
        }
    }
    
    function handleDragEnter(e) {
        if (!eyeModeActive || !draggedModule) return;
        
        e.preventDefault();
        if (this !== draggedModule) {
            this.classList.add('drag-over');
        }
    }
    
    function handleDragLeave(e) {
        if (!eyeModeActive) return;
        
        this.classList.remove('drag-over');
    }
    
    function handleDrop(e) {
        if (!eyeModeActive || !draggedModule) return;
        
        e.preventDefault();
        e.stopPropagation();
        
        const targetModule = this;
        targetModule.classList.remove('drag-over');
        
        console.log('DROP: dragged=', draggedModule.dataset.module, 'target=', targetModule.dataset.module);
        
        if (targetModule === draggedModule) {
            console.log('DROP: Same module, ignoring');
            return;
        }
        
        // Get the parent container
        const parent = targetModule.parentNode;
        if (!parent) {
            console.log('DROP: No parent found');
            return;
        }
        
        // Determine drop position based on mouse Y relative to target
        const rect = targetModule.getBoundingClientRect();
        const midY = rect.top + rect.height / 2;
        const insertBefore = e.clientY < midY;
        
        console.log('DROP: clientY=', e.clientY, 'midY=', midY, 'insertBefore=', insertBefore);
        
        // Log order BEFORE move
        const orderBefore = [];
        document.querySelectorAll('.module[data-module]').forEach(m => orderBefore.push(m.dataset.module));
        console.log('ORDER BEFORE:', orderBefore);
        
        // Move the dragged module in the DOM
        if (insertBefore) {
            // Insert before target
            parent.insertBefore(draggedModule, targetModule);
            console.log('DROP: Inserted before', targetModule.dataset.module);
        } else {
            // Insert after target
            parent.insertBefore(draggedModule, targetModule.nextSibling);
            console.log('DROP: Inserted after', targetModule.dataset.module);
        }
        
        // Log order AFTER move
        const orderAfter = [];
        document.querySelectorAll('.module[data-module]').forEach(m => orderAfter.push(m.dataset.module));
        console.log('ORDER AFTER:', orderAfter);
        
        // Remove placeholder if exists
        if (dragPlaceholder && dragPlaceholder.parentNode) {
            dragPlaceholder.parentNode.removeChild(dragPlaceholder);
            dragPlaceholder = null;
        }
        
        // Reset opacity immediately
        draggedModule.style.opacity = '1';
        draggedModule.classList.remove('module-dragging');
        
        // Save new order to server
        saveModuleOrder(orderAfter);
        
        // Clear dragged module reference
        draggedModule = null;
    }
    
    function handleMainDrop(e) {
        if (!eyeModeActive || !draggedModule) return;
        
        e.preventDefault();
        e.stopPropagation();
        
        // Find the module closest to the drop point
        const modules = document.querySelectorAll('.module[data-module]');
        let targetModule = null;
        let insertBefore = true;
        
        modules.forEach(function(mod) {
            if (mod === draggedModule) return;
            const rect = mod.getBoundingClientRect();
            if (e.clientY >= rect.top && e.clientY <= rect.bottom) {
                targetModule = mod;
                insertBefore = e.clientY < (rect.top + rect.height / 2);
            }
        });
        
        // If no target found, find the closest one
        if (!targetModule) {
            let minDist = Infinity;
            modules.forEach(function(mod) {
                if (mod === draggedModule) return;
                const rect = mod.getBoundingClientRect();
                const modCenter = rect.top + rect.height / 2;
                const dist = Math.abs(e.clientY - modCenter);
                if (dist < minDist) {
                    minDist = dist;
                    targetModule = mod;
                    insertBefore = e.clientY < modCenter;
                }
            });
        }
        
        if (!targetModule || targetModule === draggedModule) {
            // Clean up
            draggedModule.style.opacity = '1';
            draggedModule.classList.remove('module-dragging');
            if (dragPlaceholder && dragPlaceholder.parentNode) {
                dragPlaceholder.parentNode.removeChild(dragPlaceholder);
                dragPlaceholder = null;
            }
            draggedModule = null;
            return;
        }
        
        // Move the module
        const parent = targetModule.parentNode;
        if (insertBefore) {
            parent.insertBefore(draggedModule, targetModule);
        } else {
            parent.insertBefore(draggedModule, targetModule.nextSibling);
        }
        
        // Get new order
        const orderAfter = [];
        document.querySelectorAll('.module[data-module]').forEach(m => orderAfter.push(m.dataset.module));
        
        // Cleanup
        if (dragPlaceholder && dragPlaceholder.parentNode) {
            dragPlaceholder.parentNode.removeChild(dragPlaceholder);
            dragPlaceholder = null;
        }
        draggedModule.style.opacity = '1';
        draggedModule.classList.remove('module-dragging');
        
        // Save
        saveModuleOrder(orderAfter);
        draggedModule = null;
    }

    async function saveModuleOrder(order) {
        showSaving();
        
        try {
            const response = await fetch('/api/admin/module/reorder', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
                body: JSON.stringify({ order: order }),
            });
            
            if (response.ok) {
                showSaveSuccess();
            } else if (response.status === 401) {
                showSessionExpiredModal();
            } else {
                let errorMessage = 'Speichern fehlgeschlagen';
                try {
                    const data = await response.json();
                    // Handle various error response formats
                    if (typeof data.message === 'string') {
                        errorMessage = data.message;
                    } else if (typeof data.detail === 'string') {
                        errorMessage = data.detail;
                    } else if (data.detail && typeof data.detail.message === 'string') {
                        errorMessage = data.detail.message;
                    }
                    console.error('Module reorder failed:', response.status, data);
                } catch (e) {
                    // Response was not JSON
                    console.error('Module reorder failed:', response.status);
                }
                showSaveError(errorMessage);
                // Reload to restore original order
                setTimeout(() => window.location.reload(), 1500);
            }
        } catch (error) {
            showSaveError('Netzwerkfehler');
            setTimeout(() => window.location.reload(), 1500);
        }
    }
    
    // ========================================
    // Undo Button
    // ========================================
    
    if (undoBtn) {
        undoBtn.addEventListener('click', async function() {
            try {
                const response = await fetch('/api/admin/undo', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'same-origin',
                });
                
                if (response.ok) {
                    const data = await response.json();
                    showToast(data.message || 'Änderung rückgängig gemacht', 'success');
                    // Reload page to reflect changes
                    setTimeout(() => window.location.reload(), 500);
                } else if (response.status === 401) {
                    // Session expired
                    showSessionExpiredModal();
                } else {
                    const data = await response.json();
                    showToast(data.message || 'Keine Änderungen zum Rückgängigmachen', 'error');
                }
            } catch (error) {
                showToast('Netzwerkfehler', 'error');
            }
        });
    }
    
    // ========================================
    // Dropdown Menu
    // ========================================
    
    if (menuToggle && adminDropdown) {
        menuToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            adminDropdown.classList.toggle('active');
        });
        
        document.addEventListener('click', function(e) {
            if (!adminDropdown.contains(e.target) && !menuToggle.contains(e.target)) {
                adminDropdown.classList.remove('active');
            }
        });
    }
    
    // ========================================
    // Editable Fields
    // ========================================
    
    // Track original content for change detection
    const originalContent = new Map();
    
    document.querySelectorAll('[data-editable="true"]').forEach(function(element) {
        // Store original content
        originalContent.set(element, element.innerText.trim());
        
        // Handle focus
        element.addEventListener('focus', function() {
            this.dataset.focused = 'true';
        });
        
        // Handle blur (save on blur)
        element.addEventListener('blur', function() {
            delete this.dataset.focused;
            const newContent = this.innerText.trim();
            const original = originalContent.get(this);
            
            if (newContent !== original) {
                saveField(this);
                originalContent.set(this, newContent);
            }
        });
        
        // Handle paste - strip formatting
        element.addEventListener('paste', function(e) {
            e.preventDefault();
            const text = e.clipboardData.getData('text/plain');
            document.execCommand('insertText', false, text);
        });
        
        // Prevent line breaks in single-line fields. Multi-line rich-text
        // fields (about/faq/media) keep Enter for new paragraphs.
        const multiLineClasses = ['about-text', 'faq-answer', 'media-text'];
        const isMultiLine = multiLineClasses.some(function(c) { return element.classList.contains(c); });
        if (!isMultiLine) {
            element.addEventListener('keydown', function(e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.blur();
                }
            });
        }
    });
    
    // ========================================
    // Save Function
    // ========================================
    
    async function saveField(element) {
        const field = element.dataset.field;
        const subfield = element.dataset.subfield;
        const index = element.dataset.index;
        
        if (!field) return;
        
        showSaving();
        
        // All editable elements are contenteditable text nodes.
        const value = element.innerText.trim();
        
        const payload = {
            field: field,
            value: value,
        };
        
        if (subfield) payload.subfield = subfield;
        if (index !== undefined) payload.index = parseInt(index);
        
        try {
            const response = await fetch('/api/admin/content', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
                body: JSON.stringify(payload),
            });
            
            if (response.ok) {
                showSaveSuccess();
            } else {
                const data = await response.json();
                showSaveError(data.error || 'Speichern fehlgeschlagen');
            }
        } catch (error) {
            showSaveError('Netzwerkfehler');
        }
    }
    
    // ========================================
    // Saving Indicator
    // ========================================
    
    let savingIndicator = null;
    
    function createSavingIndicator() {
        if (savingIndicator) return savingIndicator;
        
        savingIndicator = document.createElement('div');
        savingIndicator.className = 'saving-indicator';
        savingIndicator.innerHTML = '<div class="saving-spinner"></div><span>Speichern...</span>';
        document.body.appendChild(savingIndicator);
        
        return savingIndicator;
    }
    
    function showSaving() {
        const indicator = createSavingIndicator();
        indicator.className = 'saving-indicator active';
        indicator.innerHTML = '<div class="saving-spinner"></div><span>Speichern...</span>';
    }
    
    function showSaveSuccess() {
        const indicator = createSavingIndicator();
        indicator.className = 'saving-indicator active success';
        indicator.innerHTML = '<span>✓ Gespeichert</span>';
        
        setTimeout(() => {
            indicator.classList.remove('active');
        }, 2000);
    }
    
    function showSaveError(message) {
        const indicator = createSavingIndicator();
        indicator.className = 'saving-indicator active error';
        indicator.innerHTML = `<span>✗ ${message}</span>`;
        
        setTimeout(() => {
            indicator.classList.remove('active');
        }, 3000);
    }
    
    // ========================================
    // Toast Notifications
    // ========================================
    
    let toastContainer = null;
    
    function getToastContainer() {
        if (toastContainer) return toastContainer;
        
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container';
        document.body.appendChild(toastContainer);
        
        return toastContainer;
    }
    
    function showToast(message, type = 'info') {
        const container = getToastContainer();
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    // ========================================
    // Add/Remove Item Handlers
    // ========================================
    
    // Handle add item buttons
    document.querySelectorAll('.btn-add-item, .btn-add-block').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const field = this.dataset.field;
            const type = this.dataset.type;
            
            // Show appropriate modal or prompt
            if (type) {
                addBlock(field, type);
            } else {
                addItem(field);
            }
        });
    });
    
    // Handle review link button
    document.querySelectorAll('.btn-add-review-link').forEach(function(btn) {
        btn.addEventListener('click', function() {
            showReviewLinkModal();
        });
    });
    
    function showReviewLinkModal() {
        // Create modal for review link
        let modal = document.getElementById('review-link-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'review-link-modal';
            modal.className = 'upload-modal-overlay';
            modal.innerHTML = `
                <div class="upload-modal">
                    <div class="upload-modal-header">
                        <h3 class="upload-modal-title">Bewertungslink hinzufügen</h3>
                        <button class="upload-modal-close" onclick="this.closest('.upload-modal-overlay').classList.remove('active')">×</button>
                    </div>
                    <div class="upload-modal-body">
                        <div style="margin-bottom: var(--spacing-md);">
                            <label style="display: block; margin-bottom: var(--spacing-xs); font-weight: 500;">Link-Text</label>
                            <input type="text" id="review-link-text" placeholder="z.B. Mehr Bewertungen auf Google" style="width: 100%; padding: var(--spacing-sm); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
                        </div>
                        <div style="margin-bottom: var(--spacing-lg);">
                            <label style="display: block; margin-bottom: var(--spacing-xs); font-weight: 500;">URL</label>
                            <input type="url" id="review-link-url" placeholder="https://..." style="width: 100%; padding: var(--spacing-sm); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
                        </div>
                        <button id="review-link-save" class="btn btn-primary" style="width: 100%;">Speichern</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            
            document.getElementById('review-link-save').addEventListener('click', async function() {
                const text = document.getElementById('review-link-text').value.trim();
                const url = document.getElementById('review-link-url').value.trim();
                
                if (!text || !url) {
                    showToast('Bitte beide Felder ausfüllen', 'error');
                    return;
                }
                
                modal.classList.remove('active');
                showSaving();
                
                try {
                    // Save both fields
                    const response1 = await fetch('/api/admin/content', {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
                        body: JSON.stringify({ field: 'review_source_text', value: text }),
                    });
                    
                    const response2 = await fetch('/api/admin/content', {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
                        body: JSON.stringify({ field: 'review_source_url', value: url }),
                    });
                    
                    if (response1.ok && response2.ok) {
                        showSaveSuccess();
                        setTimeout(() => window.location.reload(), 500);
                    } else {
                        showSaveError('Speichern fehlgeschlagen');
                    }
                } catch (error) {
                    showSaveError('Netzwerkfehler');
                }
            });
            }
        
        // Reset fields and show
        document.getElementById('review-link-text').value = '';
        document.getElementById('review-link-url').value = '';
        modal.classList.add('active');
    }
    
    // Handle add contact info button
    const addContactInfoBtn = document.getElementById('add-contact-info');
    if (addContactInfoBtn) {
        addContactInfoBtn.addEventListener('click', function() {
            showContactInfoModal();
        });
    }
    
    function showContactInfoModal() {
        let modal = document.getElementById('contact-info-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'contact-info-modal';
            modal.className = 'upload-modal-overlay';
            modal.innerHTML = `
                <div class="upload-modal">
                    <div class="upload-modal-header">
                        <h3 class="upload-modal-title">Kontaktdaten hinzufügen</h3>
                        <button class="upload-modal-close" onclick="this.closest('.upload-modal-overlay').classList.remove('active')">×</button>
                    </div>
                    <div class="upload-modal-body">
                        <div style="margin-bottom: var(--spacing-md);">
                            <label style="display: block; margin-bottom: var(--spacing-xs); font-weight: 500;">Telefon</label>
                            <input type="tel" id="contact-info-phone" placeholder="+41 79 123 45 67" style="width: 100%; padding: var(--spacing-sm); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
                        </div>
                        <div style="margin-bottom: var(--spacing-md);">
                            <label style="display: block; margin-bottom: var(--spacing-xs); font-weight: 500;">E-Mail</label>
                            <input type="email" id="contact-info-email" placeholder="info@example.com" style="width: 100%; padding: var(--spacing-sm); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
                        </div>
                        <div style="margin-bottom: var(--spacing-md);">
                            <label style="display: block; margin-bottom: var(--spacing-xs); font-weight: 500;">Adresse</label>
                            <input type="text" id="contact-info-address" placeholder="Musterstrasse 1, 8000 Zürich" style="width: 100%; padding: var(--spacing-sm); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
                        </div>
                        <div style="margin-bottom: var(--spacing-lg);">
                            <label style="display: block; margin-bottom: var(--spacing-xs); font-weight: 500;">Google Maps Link (optional)</label>
                            <input type="url" id="contact-info-maps" placeholder="https://maps.google.com/..." style="width: 100%; padding: var(--spacing-sm); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
                        </div>
                        <div style="display: flex; gap: var(--spacing-sm);">
                            <button id="contact-info-save" class="btn btn-primary" style="flex: 1;">Speichern</button>
                            <button id="contact-info-delete" class="btn" style="flex: 1; background: var(--color-error, #dc3545); color: white; border: none;">Löschen</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            
            document.getElementById('contact-info-save').addEventListener('click', async function() {
                const phone = document.getElementById('contact-info-phone').value.trim();
                const email = document.getElementById('contact-info-email').value.trim();
                const address = document.getElementById('contact-info-address').value.trim();
                const mapsLink = document.getElementById('contact-info-maps').value.trim();
                
                if (!phone && !email && !address) {
                    showToast('Bitte mindestens ein Feld ausfüllen', 'error');
                    return;
                }
                
                modal.classList.remove('active');
                showSaving();
                
                try {
                    const updates = [];
                    if (phone) {
                        updates.push(fetch('/api/admin/content', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify({ field: 'contact_phone', value: phone }),
                        }));
                    }
                    if (email) {
                        updates.push(fetch('/api/admin/content', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify({ field: 'contact_email', value: email }),
                        }));
                    }
                    if (address) {
                        updates.push(fetch('/api/admin/content', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify({ field: 'contact_address', value: address }),
                        }));
                    }
                    if (mapsLink) {
                        updates.push(fetch('/api/admin/content', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify({ field: 'contact_maps_link', value: mapsLink }),
                        }));
                    }
                    
                    const responses = await Promise.all(updates);
                    const allOk = responses.every(r => r.ok);
                    
                    if (allOk) {
                        showSaveSuccess();
                        setTimeout(() => window.location.reload(), 500);
                    } else {
                        showSaveError('Speichern fehlgeschlagen');
                    }
                } catch (error) {
                    showSaveError('Netzwerkfehler');
                }
            });
            
            document.getElementById('contact-info-delete').addEventListener('click', async function() {
                if (!confirm('Alle Kontaktdaten wirklich löschen?')) return;
                
                modal.classList.remove('active');
                showSaving();
                
                try {
                    const updates = [
                        fetch('/api/admin/content', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify({ field: 'contact_phone', value: '' }),
                        }),
                        fetch('/api/admin/content', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify({ field: 'contact_email', value: '' }),
                        }),
                        fetch('/api/admin/content', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify({ field: 'contact_address', value: '' }),
                        }),
                        fetch('/api/admin/content', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify({ field: 'contact_maps_link', value: '' }),
                        }),
                    ];
                    
                    const responses = await Promise.all(updates);
                    const allOk = responses.every(r => r.ok);
                    
                    if (allOk) {
                        showSaveSuccess();
                        setTimeout(() => window.location.reload(), 500);
                    } else {
                        showSaveError('Löschen fehlgeschlagen');
                    }
                } catch (error) {
                    showSaveError('Netzwerkfehler');
                }
            });
        }
        
        // Reset fields and show
        document.getElementById('contact-info-phone').value = '';
        document.getElementById('contact-info-email').value = '';
        document.getElementById('contact-info-address').value = '';
        document.getElementById('contact-info-maps').value = '';
        modal.classList.add('active');
    }
    
    // Handle social link clicks in admin mode (edit/remove)
    document.querySelectorAll('.social-link-admin').forEach(function(link) {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            showSocialLinkModal(this.dataset.index, this.dataset.platform, this.dataset.url, this.dataset.label);
        });
    });
    
    // Handle add social link button
    document.querySelectorAll('.btn-add-social').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            showSocialLinkModal(null, '', '', '');
        });
    });
    
    function showSocialLinkModal(index, platform, url, label) {
        const isEdit = index !== null;
        let modal = document.getElementById('social-link-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'social-link-modal';
            modal.className = 'upload-modal-overlay';
            modal.innerHTML = `
                <div class="upload-modal">
                    <div class="upload-modal-header">
                        <h3 class="upload-modal-title" id="social-modal-title">Social Link</h3>
                        <button class="upload-modal-close" onclick="this.closest('.upload-modal-overlay').classList.remove('active')">×</button>
                    </div>
                    <div class="upload-modal-body">
                        <div style="margin-bottom: var(--spacing-md);">
                            <label style="display: block; margin-bottom: var(--spacing-xs); font-weight: 500;">Plattform</label>
                            <select id="social-link-platform" style="width: 100%; padding: var(--spacing-sm); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
                                <option value="instagram">Instagram</option>
                                <option value="facebook">Facebook</option>
                                <option value="youtube">YouTube</option>
                                <option value="spotify">Spotify</option>
                                <option value="email">E-Mail</option>
                                <option value="custom">Anderer Link</option>
                            </select>
                        </div>
                        <div style="margin-bottom: var(--spacing-md);">
                            <label style="display: block; margin-bottom: var(--spacing-xs); font-weight: 500;">URL</label>
                            <input type="url" id="social-link-url" placeholder="https://..." style="width: 100%; padding: var(--spacing-sm); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
                        </div>
                        <div style="margin-bottom: var(--spacing-lg);">
                            <label style="display: block; margin-bottom: var(--spacing-xs); font-weight: 500;">Label (optional)</label>
                            <input type="text" id="social-link-label" placeholder="z.B. Folge uns auf Instagram" style="width: 100%; padding: var(--spacing-sm); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
                        </div>
                        <div style="display: flex; gap: var(--spacing-sm);">
                            <button id="social-link-save" class="btn btn-primary" style="flex: 1;">Speichern</button>
                            <button id="social-link-delete" class="btn btn-danger" style="display: none;">Löschen</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            
            document.getElementById('social-link-save').addEventListener('click', async function() {
                const platform = document.getElementById('social-link-platform').value;
                const url = document.getElementById('social-link-url').value.trim();
                const label = document.getElementById('social-link-label').value.trim();
                const editIndex = modal.dataset.editIndex;
                
                if (!url) {
                    showToast('Bitte URL eingeben', 'error');
                    return;
                }
                
                modal.classList.remove('active');
                showSaving();
                
                try {
                    let response;
                    if (editIndex !== '') {
                        // Update existing
                        response = await fetch('/api/admin/content', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify({
                                field: 'footer_social_links',
                                index: parseInt(editIndex),
                                value: { platform, url, label: label || platform }
                            }),
                        });
                    } else {
                        // Add new
                        response = await fetch('/api/admin/content/add', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            credentials: 'same-origin',
                            body: JSON.stringify({
                                field: 'footer_social_links',
                                item: { platform, url, label: label || platform }
                            }),
                        });
                    }
                    
                    if (response.ok) {
                        showSaveSuccess();
                        setTimeout(() => window.location.reload(), 500);
                    } else {
                        showSaveError('Speichern fehlgeschlagen');
                    }
                } catch (error) {
                    showSaveError('Netzwerkfehler');
                }
            });
            
            document.getElementById('social-link-delete').addEventListener('click', async function() {
                const editIndex = modal.dataset.editIndex;
                if (editIndex === '' || !confirm('Social Link wirklich löschen?')) return;
                
                modal.classList.remove('active');
                showSaving();
                
                try {
                    const response = await fetch('/api/admin/content/remove', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
                        body: JSON.stringify({
                            field: 'footer_social_links',
                            index: parseInt(editIndex)
                        }),
                    });
                    
                    if (response.ok) {
                        showSaveSuccess();
                        setTimeout(() => window.location.reload(), 500);
                    } else {
                        showSaveError('Löschen fehlgeschlagen');
                    }
                } catch (error) {
                    showSaveError('Netzwerkfehler');
                }
            });
        }
        
        // Set values and show
        document.getElementById('social-modal-title').textContent = isEdit ? 'Social Link bearbeiten' : 'Social Link hinzufügen';
        document.getElementById('social-link-platform').value = platform || 'instagram';
        document.getElementById('social-link-url').value = url || '';
        document.getElementById('social-link-label').value = label || '';
        document.getElementById('social-link-delete').style.display = isEdit ? 'block' : 'none';
        modal.dataset.editIndex = index !== null ? index : '';
        modal.classList.add('active');
    }
    
    // Handle remove item buttons
    document.querySelectorAll('.btn-remove-item, .btn-remove-block').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const field = this.dataset.field;
            const index = this.dataset.index;
            
            if (confirm('Möchten Sie dieses Element wirklich entfernen?')) {
                removeItem(field, index);
            }
        });
    });
    
    async function addItem(field) {
        showSaving();
        
        try {
            const response = await fetch('/api/admin/content/add', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
                body: JSON.stringify({ field: field, item: {} }),
            });
            
            if (response.ok) {
                showSaveSuccess();
                // Reload page to show new item
                setTimeout(() => window.location.reload(), 500);
            } else if (response.status === 401) {
                showSessionExpiredModal();
            } else {
                const data = await response.json();
                showSaveError(data.message || 'Hinzufügen fehlgeschlagen');
            }
        } catch (error) {
            showSaveError('Netzwerkfehler');
        }
    }
    
    async function addBlock(field, type) {
        // For media types that need input, show appropriate modal
        if (type === 'youtube') {
            showYoutubeModal(field);
            return;
        }
        if (type === 'audio') {
            showAudioModal(field);
            return;
        }
        if (type === 'image') {
            showImageUploadForBlock(field);
            return;
        }
        
        // For text/gallery, just create the block directly
        showSaving();
        
        try {
            const response = await fetch('/api/admin/content/add', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
                body: JSON.stringify({ field: field, item: { type: type } }),
            });
            
            if (response.ok) {
                showSaveSuccess();
                setTimeout(() => window.location.reload(), 500);
            } else if (response.status === 401) {
                showSessionExpiredModal();
            } else {
                const data = await response.json();
                showSaveError(data.message || 'Hinzufügen fehlgeschlagen');
            }
        } catch (error) {
            showSaveError('Netzwerkfehler');
        }
    }
    
    function showYoutubeModal(field) {
        let modal = document.getElementById('youtube-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'youtube-modal';
            modal.className = 'upload-modal-overlay';
            modal.innerHTML = `
                <div class="upload-modal">
                    <div class="upload-modal-header">
                        <h3 class="upload-modal-title">YouTube Video hinzufügen</h3>
                        <button class="upload-modal-close" onclick="this.closest('.upload-modal-overlay').classList.remove('active')">×</button>
                    </div>
                    <div class="upload-modal-body">
                        <div style="margin-bottom: var(--spacing-lg);">
                            <label style="display: block; margin-bottom: var(--spacing-xs); font-weight: 500;">YouTube URL</label>
                            <input type="url" id="youtube-url-input" placeholder="https://www.youtube.com/watch?v=..." style="width: 100%; padding: var(--spacing-sm); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
                            <small style="color: var(--color-text-muted); display: block; margin-top: var(--spacing-xs);">Unterstützt: youtube.com/watch, youtu.be Links</small>
                        </div>
                        <button id="youtube-save" class="btn btn-primary" style="width: 100%;">Hinzufügen</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
        
        const input = document.getElementById('youtube-url-input');
        input.value = '';
        modal.classList.add('active');
        input.focus();
        
        // Remove old listener and add new one
        const saveBtn = document.getElementById('youtube-save');
        const newSaveBtn = saveBtn.cloneNode(true);
        saveBtn.parentNode.replaceChild(newSaveBtn, saveBtn);
        
        newSaveBtn.addEventListener('click', async function() {
            const url = input.value.trim();
            if (!url) {
                showToast('Bitte eine YouTube URL eingeben', 'error');
                return;
            }
            
            modal.classList.remove('active');
            await addBlockWithData(field, { type: 'youtube', youtube_url: url });
        });
    }
    
    function showAudioModal(field) {
        let modal = document.getElementById('audio-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'audio-modal';
            modal.className = 'upload-modal-overlay';
            modal.innerHTML = `
                <div class="upload-modal">
                    <div class="upload-modal-header">
                        <h3 class="upload-modal-title">Audio hinzufügen</h3>
                        <button class="upload-modal-close" onclick="this.closest('.upload-modal-overlay').classList.remove('active')">×</button>
                    </div>
                    <div class="upload-modal-body">
                        <div style="margin-bottom: var(--spacing-md);">
                            <label style="display: block; margin-bottom: var(--spacing-xs); font-weight: 500;">Plattform</label>
                            <select id="audio-provider-input" style="width: 100%; padding: var(--spacing-sm); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
                                <option value="spotify">Spotify</option>
                                <option value="soundcloud">SoundCloud</option>
                                <option value="other">Andere</option>
                            </select>
                        </div>
                        <div style="margin-bottom: var(--spacing-lg);">
                            <label style="display: block; margin-bottom: var(--spacing-xs); font-weight: 500;">Audio URL / Embed Code</label>
                            <input type="text" id="audio-url-input" placeholder="https://open.spotify.com/track/..." style="width: 100%; padding: var(--spacing-sm); border: 1px solid var(--color-border); border-radius: var(--border-radius);">
                        </div>
                        <button id="audio-save" class="btn btn-primary" style="width: 100%;">Hinzufügen</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
        
        const urlInput = document.getElementById('audio-url-input');
        const providerInput = document.getElementById('audio-provider-input');
        urlInput.value = '';
        providerInput.value = 'spotify';
        modal.classList.add('active');
        urlInput.focus();
        
        // Remove old listener and add new one  
        const saveBtn = document.getElementById('audio-save');
        const newSaveBtn = saveBtn.cloneNode(true);
        saveBtn.parentNode.replaceChild(newSaveBtn, saveBtn);
        
        newSaveBtn.addEventListener('click', async function() {
            const url = urlInput.value.trim();
            const provider = providerInput.value;
            if (!url) {
                showToast('Bitte eine Audio URL eingeben', 'error');
                return;
            }
            
            modal.classList.remove('active');
            await addBlockWithData(field, { type: 'audio', audio_url: url, audio_provider: provider });
        });
    }
    
    function showImageUploadForBlock(field) {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        
        input.addEventListener('change', async function() {
            if (!this.files || !this.files[0]) return;
            
            const file = this.files[0];
            const formData = new FormData();
            formData.append('file', file);
            
            showSaving();
            
            try {
                // Step 1: Upload the file
                const uploadResponse = await fetch('/api/admin/upload', {
                    method: 'POST',
                    credentials: 'same-origin',
                    body: formData,
                });
                
                if (!uploadResponse.ok) {
                    const data = await uploadResponse.json();
                    if (uploadResponse.status === 401) {
                        showSessionExpiredModal();
                        return;
                    }
                    throw new Error(data.detail?.message || 'Upload fehlgeschlagen');
                }
                
                const uploadData = await uploadResponse.json();
                const fileUrl = uploadData.default_src;
                if (!fileUrl) {
                    throw new Error('Upload-Antwort enthält keine Bild-URL');
                }
                
                // Step 2: Add block with image URL
                await addBlockWithData(field, { type: 'image', src: fileUrl, alt: '' });
            } catch (error) {
                showSaveError(error.message || 'Netzwerkfehler');
            }
        });
        
        input.click();
    }
    
    async function addBlockWithData(field, item) {
        showSaving();
        
        try {
            const response = await fetch('/api/admin/content/add', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
                body: JSON.stringify({ field: field, item: item }),
            });
            
            if (response.ok) {
                showSaveSuccess();
                setTimeout(() => window.location.reload(), 500);
            } else if (response.status === 401) {
                showSessionExpiredModal();
            } else {
                const data = await response.json();
                showSaveError(data.message || 'Hinzufügen fehlgeschlagen');
            }
        } catch (error) {
            showSaveError('Netzwerkfehler');
        }
    }
    
    async function removeItem(field, index) {
        showSaving();
        
        try {
            const response = await fetch('/api/admin/content/remove', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
                body: JSON.stringify({ field: field, index: parseInt(index) }),
            });
            
            if (response.ok) {
                showSaveSuccess();
                // Reload to show changes
                setTimeout(() => window.location.reload(), 500);
            } else if (response.status === 401) {
                showSessionExpiredModal();
            } else {
                const data = await response.json();
                showSaveError(data.message || 'Entfernen fehlgeschlagen');
            }
        } catch (error) {
            showSaveError('Netzwerkfehler');
        }
    }
    
    // ========================================
    // Session Expired Modal
    // ========================================
    
    function showSessionExpiredModal() {
        // Create modal if not exists
        let modal = document.getElementById('session-expired-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'session-expired-modal';
            modal.className = 'upload-modal-overlay';
            modal.innerHTML = `
                <div class="upload-modal">
                    <div class="upload-modal-header">
                        <h3 class="upload-modal-title">Sitzung abgelaufen</h3>
                    </div>
                    <p style="margin-bottom: var(--spacing-lg);">Ihre Sitzung ist abgelaufen. Bitte melden Sie sich erneut an.</p>
                    <a href="/admin/login" class="btn btn-primary" style="width: 100%; text-align: center;">Zur Anmeldung</a>
                </div>
            `;
            document.body.appendChild(modal);
        }
        modal.classList.add('active');
    }
    
    // ========================================
    // Image Upload Handlers
    // ========================================
    
    document.querySelectorAll('.btn-image-upload, .btn-change-image, .btn-add-image').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const field = this.closest('[data-field]')?.dataset.field;
            if (field) {
                openContentImageUpload(field);
            }
        });
    });
    
    function openContentImageUpload(field) {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        
        input.addEventListener('change', async function() {
            if (!this.files || !this.files[0]) return;
            
            const file = this.files[0];
            const formData = new FormData();
            formData.append('file', file);
            
            showSaving();
            
            try {
                // Step 1: Upload the file to get a file_id
                const uploadResponse = await fetch('/api/admin/upload', {
                    method: 'POST',
                    credentials: 'same-origin',
                    body: formData,
                });
                
                if (!uploadResponse.ok) {
                    const data = await uploadResponse.json();
                    if (uploadResponse.status === 401) {
                        showSessionExpiredModal();
                        return;
                    }
                    throw new Error(data.detail?.message || data.error || 'Upload fehlgeschlagen');
                }
                
                const uploadData = await uploadResponse.json();
                const fileId = uploadData.file_id;
                
                // Step 2: Update the content image field
                const updateResponse = await fetch(`/api/admin/content/image/${field}`, {
                    method: 'PUT',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ file_id: fileId }),
                });
                
                if (updateResponse.ok) {
                    showSaveSuccess();
                    // Reload to show updated image
                    window.location.reload();
                } else {
                    const data = await updateResponse.json();
                    if (updateResponse.status === 401) {
                        showSessionExpiredModal();
                    } else {
                        showSaveError(data.detail?.message || 'Bild Update fehlgeschlagen');
                    }
                }
            } catch (error) {
                showSaveError(error.message || 'Netzwerkfehler');
                console.error('Content image upload error:', error);
            }
        });
        
        input.click();
    }
    
    // ========================================
    // Nav Label Editing
    // ========================================
    
    // Track original nav labels for change detection
    const originalNavLabels = new Map();
    
    document.querySelectorAll('[data-nav-editable]').forEach(function(element) {
        // Store original content
        originalNavLabels.set(element, element.innerText.trim());
        
        // Make editable on click
        element.addEventListener('click', function(e) {
            // Prevent navigation when clicking to edit
            e.preventDefault();
            
            // Set contenteditable
            this.contentEditable = 'true';
            this.focus();
            
            // Select all text
            const range = document.createRange();
            range.selectNodeContents(this);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
        });
        
        // Handle blur (save on blur)
        element.addEventListener('blur', function() {
            this.contentEditable = 'false';
            const newLabel = this.innerText.trim();
            const original = originalNavLabels.get(this);
            
            if (newLabel !== original) {
                saveNavLabel(this);
                originalNavLabels.set(this, newLabel);
            }
        });
        
        // Handle paste - strip formatting
        element.addEventListener('paste', function(e) {
            e.preventDefault();
            const text = e.clipboardData.getData('text/plain');
            document.execCommand('insertText', false, text);
        });
        
        // Prevent line breaks
        element.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.blur();
            } else if (e.key === 'Escape') {
                // Restore original on Escape
                this.innerText = originalNavLabels.get(this) || '';
                this.blur();
            }
        });
    });
    
    async function saveNavLabel(element) {
        const module = element.dataset.navEditable;
        const label = element.innerText.trim();
        
        if (!module) return;
        
        showSaving();
        
        try {
            const response = await fetch('/api/admin/config/nav-labels', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    module: module,
                    label: label,
                }),
            });
            
            if (response.ok) {
                showSaveSuccess();
                if (!label) {
                    // If label was cleared, reload to get default (nav + section header)
                    window.location.reload();
                } else {
                    // Single source of truth: keep nav label and section header in sync
                    document.querySelectorAll('[data-nav-editable="' + module + '"]').forEach(function(el) {
                        if (el !== element) {
                            el.innerText = label;
                            originalNavLabels.set(el, label);
                        }
                    });
                }
            } else {
                const data = await response.json();
                if (response.status === 401) {
                    showSessionExpiredModal();
                } else {
                    showSaveError(data.detail?.message || 'Speichern fehlgeschlagen');
                }
            }
        } catch (error) {
            showSaveError('Netzwerkfehler');
            console.error('Nav label save error:', error);
        }
    }
    
    // Expose functions globally for inline handlers
    window.adminShowToast = showToast;
    
    // ========================================
    // Logo and Favicon Upload Handlers
    // ========================================
    
    // Logo click handler
    const logoElement = document.querySelector('[data-logo-editable]');
    if (logoElement) {
        logoElement.addEventListener('click', function(e) {
            e.preventDefault();
            openImageUpload('logo');
        });
    }
    
    // Favicon button handler
    const faviconBtn = document.getElementById('favicon-upload-btn');
    if (faviconBtn) {
        faviconBtn.addEventListener('click', function(e) {
            e.preventDefault();
            openImageUpload('favicon');
        });
    }
    
    function openImageUpload(type) {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = type === 'favicon' ? 'image/x-icon,image/png,image/ico,.ico' : 'image/*';
        
        input.addEventListener('change', async function() {
            if (!this.files || !this.files[0]) return;
            
            const file = this.files[0];
            const formData = new FormData();
            formData.append('file', file);
            
            showSaving();
            
            try {
                // Step 1: Upload the file to get a file_id
                const uploadResponse = await fetch('/api/admin/upload', {
                    method: 'POST',
                    credentials: 'same-origin',
                    body: formData,
                });
                
                if (!uploadResponse.ok) {
                    const data = await uploadResponse.json();
                    if (uploadResponse.status === 401) {
                        showSessionExpiredModal();
                        return;
                    }
                    throw new Error(data.detail?.message || data.error || 'Upload fehlgeschlagen');
                }
                
                const uploadData = await uploadResponse.json();
                const fileId = uploadData.file_id;
                
                // Step 2: Update the logo/favicon config with the file_id
                const configResponse = await fetch(`/api/admin/config/${type}`, {
                    method: 'PUT',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ file_id: fileId }),
                });
                
                if (configResponse.ok) {
                    showSaveSuccess();
                    // Reload to show updated logo/favicon
                    window.location.reload();
                } else {
                    const data = await configResponse.json();
                    if (configResponse.status === 401) {
                        showSessionExpiredModal();
                    } else {
                        showSaveError(data.detail?.message || `${type} Update fehlgeschlagen`);
                    }
                }
            } catch (error) {
                showSaveError(error.message || 'Netzwerkfehler');
                console.error(`${type} upload error:`, error);
            }
        });
        
        input.click();
    }
    
    // ========================================
    // Media Block Drag & Drop Reordering
    // ========================================
    
    let draggedBlock = null;
    
    function initMediaBlockReorder() {
        const containers = document.querySelectorAll('.media-blocks');
        containers.forEach(function(container) {
            const blocks = container.querySelectorAll('.media-block[data-block-index]');
            if (blocks.length < 2) return;
            
            blocks.forEach(function(block) {
                // Add a drag handle. The handle itself is the draggable element so
                // contenteditable text blocks stay fully editable/selectable.
                if (!block.querySelector('.block-drag-handle')) {
                    const handle = document.createElement('div');
                    handle.className = 'block-drag-handle';
                    handle.setAttribute('draggable', 'true');
                    handle.setAttribute('role', 'button');
                    handle.title = 'Ziehen zum Sortieren';
                    handle.setAttribute('aria-label', 'Block verschieben');
                    handle.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="6" r="1"></circle><circle cx="15" cy="6" r="1"></circle><circle cx="9" cy="12" r="1"></circle><circle cx="15" cy="12" r="1"></circle><circle cx="9" cy="18" r="1"></circle><circle cx="15" cy="18" r="1"></circle></svg>';
                    
                    handle.addEventListener('dragstart', handleBlockDragStart);
                    handle.addEventListener('dragend', handleBlockDragEnd);
                    
                    block.appendChild(handle);
                }
                
                block.addEventListener('dragover', handleBlockDragOver);
                block.addEventListener('drop', handleBlockDrop);
            });
        });
    }
    
    function handleBlockDragStart(e) {
        // Don't interfere with module reordering in eye mode.
        if (document.body.classList.contains('eye-mode-active')) return;
        
        const block = this.closest('.media-block');
        if (!block) return;
        
        draggedBlock = block;
        block.classList.add('block-dragging');
        e.dataTransfer.effectAllowed = 'move';
        try {
            e.dataTransfer.setData('text/plain', block.dataset.blockIndex || '');
            // Use the whole block as the drag image instead of just the handle.
            if (e.dataTransfer.setDragImage) {
                e.dataTransfer.setDragImage(block, 20, 20);
            }
        } catch (err) { /* ignore */ }
    }
    
    function handleBlockDragEnd() {
        if (draggedBlock) {
            draggedBlock.classList.remove('block-dragging');
        }
        document.querySelectorAll('.media-block.block-drag-over').forEach(function(b) {
            b.classList.remove('block-drag-over');
        });
        draggedBlock = null;
    }
    
    function handleBlockDragOver(e) {
        if (!draggedBlock || this === draggedBlock) return;
        if (this.parentNode !== draggedBlock.parentNode) return;
        
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        
        const rect = this.getBoundingClientRect();
        const midY = rect.top + rect.height / 2;
        if (e.clientY < midY) {
            this.parentNode.insertBefore(draggedBlock, this);
        } else {
            this.parentNode.insertBefore(draggedBlock, this.nextSibling);
        }
    }
    
    function handleBlockDrop(e) {
        if (!draggedBlock) return;
        e.preventDefault();
        e.stopPropagation();
        
        const container = draggedBlock.parentNode;
        // Build the new order from the original indices in their current DOM order.
        const order = [];
        container.querySelectorAll('.media-block[data-block-index]').forEach(function(b) {
            order.push(parseInt(b.dataset.blockIndex, 10));
        });
        
        saveBlockOrder('media_blocks', order);
    }
    
    async function saveBlockOrder(field, order) {
        showSaving();
        
        try {
            const response = await fetch('/api/admin/content/reorder', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
                body: JSON.stringify({ field: field, order: order }),
            });
            
            if (response.ok) {
                showSaveSuccess();
                setTimeout(() => window.location.reload(), 500);
            } else if (response.status === 401) {
                showSessionExpiredModal();
            } else {
                const data = await response.json();
                showSaveError(data.detail?.message || data.message || 'Sortieren fehlgeschlagen');
            }
        } catch (error) {
            showSaveError('Netzwerkfehler');
        }
    }
    
    initMediaBlockReorder();
    
})();
