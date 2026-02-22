/**
 * Reel Studio - Professional Video Creator Engine
 * Canva-style video editor for creating reels
 */

const ReelStudio = {
    // State
    project: {
        name: 'Untitled Reel',
        width: 1080,
        height: 1920,
        duration: 15,
        fps: 30,
        layers: [],
        timeline: []
    },
    
    currentTool: 'templates',
    selectedLayer: null,
    isPlaying: false,
    currentTime: 0,
    
    // History for undo/redo
    history: [],
    historyIndex: -1,
    
    // Initialize
    init() {
        console.log('🎬 Reel Studio Initialized');
        this.setupEventListeners();
        this.loadTemplates();
        this.renderTimeline();
    },
    
    // Setup Event Listeners
    setupEventListeners() {
        // Tool buttons
        document.querySelectorAll('.tool-item').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tool = e.currentTarget.dataset.tool;
                this.switchTool(tool);
            });
        });
        
        // Property tabs
        document.querySelectorAll('.prop-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.switchPropertyTab(e.currentTarget.dataset.tab);
            });
        });
        
        // Canvas interactions
        const canvas = document.getElementById('canvasStage');
        canvas.addEventListener('click', (e) => this.handleCanvasClick(e));
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
    },

    
    // Switch Tool
    switchTool(tool) {
        this.currentTool = tool;
        
        // Update active state
        document.querySelectorAll('.tool-item').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-tool="${tool}"]`).classList.add('active');
        
        // Load tool content
        this.loadToolContent(tool);
    },
    
    // Load Tool Content
    loadToolContent(tool) {
        const panel = document.getElementById('panelContent');
        const title = document.getElementById('panelTitle');
        const subtitle = document.getElementById('panelSubtitle');
        
        switch(tool) {
            case 'templates':
                title.textContent = 'Templates';
                subtitle.textContent = 'Choose a template to start';
                this.loadTemplates();
                break;
            case 'images':
                title.textContent = 'Images';
                subtitle.textContent = 'Upload or choose images';
                this.loadImageUploader();
                break;
            case 'text':
                title.textContent = 'Text';
                subtitle.textContent = 'Add text to your reel';
                this.loadTextEditor();
                break;
            case 'elements':
                title.textContent = 'Elements';
                subtitle.textContent = 'Shapes, icons & stickers';
                this.loadElements();
                break;
            case 'music':
                title.textContent = 'Music';
                subtitle.textContent = 'Add background music';
                this.loadMusicLibrary();
                break;
            case 'effects':
                title.textContent = 'Effects';
                subtitle.textContent = 'Filters & effects';
                this.loadEffects();
                break;
            case 'animations':
                title.textContent = 'Animations';
                subtitle.textContent = 'Animate your elements';
                this.loadAnimations();
                break;
            case 'settings':
                title.textContent = 'Settings';
                subtitle.textContent = 'Project settings';
                this.loadSettings();
                break;
        }
    },

    
    // Load Templates
    loadTemplates() {
        const panel = document.getElementById('panelContent');
        const templates = this.getTemplates();
        
        let html = '<div class="templates-grid">';
        templates.forEach(template => {
            html += `
                <div class="template-card" onclick="ReelStudio.applyTemplate('${template.id}')">
                    <div style="background: ${template.gradient}; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; color: white; font-size: 12px;">
                        ${template.name}
                    </div>
                    <div class="template-overlay">${template.name}</div>
                </div>
            `;
        });
        html += '</div>';
        panel.innerHTML = html;
    },
    
    // Get Templates
    getTemplates() {
        return [
            { id: 'product-showcase', name: 'Product Showcase', gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' },
            { id: 'fashion-reel', name: 'Fashion Reel', gradient: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)' },
            { id: 'sale-offer', name: 'Sale Offer', gradient: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)' },
            { id: 'minimal-clean', name: 'Minimal Clean', gradient: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)' },
            { id: 'bold-modern', name: 'Bold Modern', gradient: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)' },
            { id: 'elegant-luxury', name: 'Elegant Luxury', gradient: 'linear-gradient(135deg, #30cfd0 0%, #330867 100%)' },
        ];
    },
    
    // Apply Template
    applyTemplate(templateId) {
        console.log('Applying template:', templateId);
        // Template logic here
        alert(`Template "${templateId}" applied! (Feature in development)`);
    },

    
    // Load Image Uploader
    loadImageUploader() {
        const panel = document.getElementById('panelContent');
        panel.innerHTML = `
            <div style="margin-bottom: 20px;">
                <button class="canvas-btn" style="width: 100%;" onclick="document.getElementById('studioImageInput').click()">
                    <i class="fas fa-upload"></i> Upload Images
                </button>
                <input type="file" id="studioImageInput" multiple accept="image/*" style="display: none;" onchange="ReelStudio.handleImageUpload(event)">
            </div>
            <div id="uploadedImagesList"></div>
        `;
    },
    
    // Handle Image Upload
    handleImageUpload(event) {
        const files = Array.from(event.target.files);
        files.forEach(file => {
            const reader = new FileReader();
            reader.onload = (e) => {
                this.addImageToProject(e.target.result, file.name);
            };
            reader.readAsDataURL(file);
        });
    },
    
    // Add Image to Project
    addImageToProject(imageUrl, name) {
        const layer = {
            id: Date.now(),
            type: 'image',
            name: name,
            url: imageUrl,
            x: 0,
            y: 0,
            width: 1080,
            height: 1920,
            rotation: 0,
            opacity: 1,
            startTime: this.project.timeline.length * 3,
            duration: 3,
            animation: 'zoom'
        };
        
        this.project.layers.push(layer);
        this.project.timeline.push(layer);
        this.renderCanvas();
        this.renderTimeline();
        this.updateImagesList();
    },
    
    // Update Images List
    updateImagesList() {
        const list = document.getElementById('uploadedImagesList');
        if (!list) return;
        
        let html = '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;">';
        this.project.layers.filter(l => l.type === 'image').forEach(layer => {
            html += `
                <div style="background: #1a1a1a; border-radius: 8px; padding: 10px; cursor: pointer;" onclick="ReelStudio.selectLayer(${layer.id})">
                    <img src="${layer.url}" style="width: 100%; height: 80px; object-fit: cover; border-radius: 4px; margin-bottom: 5px;">
                    <div style="font-size: 11px; color: #aaa; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${layer.name}</div>
                </div>
            `;
        });
        html += '</div>';
        list.innerHTML = html;
    },

    
    // Load Text Editor
    loadTextEditor() {
        const panel = document.getElementById('panelContent');
        panel.innerHTML = `
            <div class="prop-group">
                <label class="prop-label">Text Content</label>
                <textarea class="prop-input" id="textContent" rows="3" placeholder="Enter your text..."></textarea>
            </div>
            
            <div class="prop-group">
                <label class="prop-label">Font Family</label>
                <select class="prop-input" id="textFont">
                    <option value="Arial">Arial</option>
                    <option value="Poppins">Poppins</option>
                    <option value="Montserrat">Montserrat</option>
                    <option value="Playfair Display">Playfair Display</option>
                    <option value="Roboto">Roboto</option>
                </select>
            </div>
            
            <div class="prop-group">
                <label class="prop-label">Font Size</label>
                <input type="range" class="prop-slider" id="textSize" min="20" max="150" value="60">
                <span id="textSizeValue">60px</span>
            </div>
            
            <div class="prop-group">
                <label class="prop-label">Text Color</label>
                <div class="prop-color-picker">
                    <div class="color-swatch" style="background: #ffffff;" onclick="ReelStudio.setTextColor('#ffffff')"></div>
                    <div class="color-swatch" style="background: #000000;" onclick="ReelStudio.setTextColor('#000000')"></div>
                    <div class="color-swatch" style="background: #696cff;" onclick="ReelStudio.setTextColor('#696cff')"></div>
                    <div class="color-swatch" style="background: #ff4444;" onclick="ReelStudio.setTextColor('#ff4444')"></div>
                    <div class="color-swatch" style="background: #00ff88;" onclick="ReelStudio.setTextColor('#00ff88')"></div>
                    <div class="color-swatch" style="background: #ffaa00;" onclick="ReelStudio.setTextColor('#ffaa00')"></div>
                </div>
            </div>
            
            <div class="prop-group">
                <label class="prop-label">Text Position</label>
                <select class="prop-input" id="textPosition">
                    <option value="top">Top</option>
                    <option value="center" selected>Center</option>
                    <option value="bottom">Bottom</option>
                </select>
            </div>
            
            <button class="canvas-btn primary" style="width: 100%; margin-top: 20px;" onclick="ReelStudio.addTextLayer()">
                <i class="fas fa-plus"></i> Add Text
            </button>
        `;
        
        // Add event listeners
        document.getElementById('textSize').addEventListener('input', (e) => {
            document.getElementById('textSizeValue').textContent = e.target.value + 'px';
        });
    },
    
    // Add Text Layer
    addTextLayer() {
        const content = document.getElementById('textContent').value;
        if (!content) {
            alert('Please enter text content');
            return;
        }
        
        const font = document.getElementById('textFont').value;
        const size = document.getElementById('textSize').value;
        const position = document.getElementById('textPosition').value;
        
        const layer = {
            id: Date.now(),
            type: 'text',
            content: content,
            font: font,
            size: parseInt(size),
            color: this.currentTextColor || '#ffffff',
            position: position,
            x: 540,
            y: position === 'top' ? 200 : position === 'bottom' ? 1720 : 960,
            rotation: 0,
            opacity: 1,
            startTime: this.project.timeline.length * 3,
            duration: 3,
            animation: 'fadeIn'
        };
        
        this.project.layers.push(layer);
        this.project.timeline.push(layer);
        this.renderCanvas();
        this.renderTimeline();
        
        document.getElementById('textContent').value = '';
    },
    
    // Set Text Color
    setTextColor(color) {
        this.currentTextColor = color;
        document.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('active'));
        event.target.classList.add('active');
    },

    
    // Load Elements
    loadElements() {
        const panel = document.getElementById('panelContent');
        panel.innerHTML = `
            <div style="margin-bottom: 20px;">
                <h4 style="color: #aaa; font-size: 13px; margin-bottom: 10px;">Shapes</h4>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
                    <div class="element-btn" onclick="ReelStudio.addShape('rectangle')">
                        <i class="fas fa-square" style="font-size: 30px;"></i>
                        <div style="font-size: 10px; margin-top: 5px;">Rectangle</div>
                    </div>
                    <div class="element-btn" onclick="ReelStudio.addShape('circle')">
                        <i class="fas fa-circle" style="font-size: 30px;"></i>
                        <div style="font-size: 10px; margin-top: 5px;">Circle</div>
                    </div>
                    <div class="element-btn" onclick="ReelStudio.addShape('star')">
                        <i class="fas fa-star" style="font-size: 30px;"></i>
                        <div style="font-size: 10px; margin-top: 5px;">Star</div>
                    </div>
                </div>
            </div>
            
            <div>
                <h4 style="color: #aaa; font-size: 13px; margin-bottom: 10px;">Icons</h4>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px;">
                    <div class="element-btn" onclick="ReelStudio.addIcon('heart')">
                        <i class="fas fa-heart" style="font-size: 24px; color: #ff4444;"></i>
                    </div>
                    <div class="element-btn" onclick="ReelStudio.addIcon('star')">
                        <i class="fas fa-star" style="font-size: 24px; color: #ffaa00;"></i>
                    </div>
                    <div class="element-btn" onclick="ReelStudio.addIcon('fire')">
                        <i class="fas fa-fire" style="font-size: 24px; color: #ff6600;"></i>
                    </div>
                    <div class="element-btn" onclick="ReelStudio.addIcon('bolt')">
                        <i class="fas fa-bolt" style="font-size: 24px; color: #ffff00;"></i>
                    </div>
                    <div class="element-btn" onclick="ReelStudio.addIcon('shopping-cart')">
                        <i class="fas fa-shopping-cart" style="font-size: 24px; color: #696cff;"></i>
                    </div>
                    <div class="element-btn" onclick="ReelStudio.addIcon('tag')">
                        <i class="fas fa-tag" style="font-size: 24px; color: #00ff88;"></i>
                    </div>
                    <div class="element-btn" onclick="ReelStudio.addIcon('gift')">
                        <i class="fas fa-gift" style="font-size: 24px; color: #ff69b4;"></i>
                    </div>
                    <div class="element-btn" onclick="ReelStudio.addIcon('crown')">
                        <i class="fas fa-crown" style="font-size: 24px; color: #ffd700;"></i>
                    </div>
                </div>
            </div>
        `;
    },
    
    // Add Shape
    addShape(shape) {
        const layer = {
            id: Date.now(),
            type: 'shape',
            shape: shape,
            x: 540,
            y: 960,
            width: 200,
            height: 200,
            color: '#696cff',
            rotation: 0,
            opacity: 0.8,
            startTime: 0,
            duration: this.project.duration
        };
        
        this.project.layers.push(layer);
        this.renderCanvas();
    },
    
    // Add Icon
    addIcon(icon) {
        const layer = {
            id: Date.now(),
            type: 'icon',
            icon: icon,
            x: 540,
            y: 960,
            size: 80,
            color: '#ffffff',
            rotation: 0,
            opacity: 1,
            startTime: 0,
            duration: this.project.duration
        };
        
        this.project.layers.push(layer);
        this.renderCanvas();
    },

    
    // Load Music Library
    loadMusicLibrary() {
        const panel = document.getElementById('panelContent');
        panel.innerHTML = `
            <div style="margin-bottom: 20px;">
                <button class="canvas-btn" style="width: 100%;" onclick="document.getElementById('studioMusicInput').click()">
                    <i class="fas fa-upload"></i> Upload Music
                </button>
                <input type="file" id="studioMusicInput" accept="audio/*" style="display: none;" onchange="ReelStudio.handleMusicUpload(event)">
            </div>
            
            <div id="musicTracksList">
                <div style="color: #888; text-align: center; padding: 40px 20px;">
                    <i class="fas fa-music" style="font-size: 48px; margin-bottom: 15px; opacity: 0.3;"></i>
                    <div>No music added yet</div>
                </div>
            </div>
        `;
    },
    
    // Handle Music Upload
    handleMusicUpload(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = (e) => {
            this.project.music = {
                name: file.name,
                url: e.target.result,
                volume: 0.7
            };
            this.updateMusicList();
        };
        reader.readAsDataURL(file);
    },
    
    // Update Music List
    updateMusicList() {
        const list = document.getElementById('musicTracksList');
        if (!list || !this.project.music) return;
        
        list.innerHTML = `
            <div style="background: #1a1a1a; border-radius: 8px; padding: 15px;">
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                    <i class="fas fa-music" style="color: #696cff;"></i>
                    <div style="flex: 1; font-size: 13px;">${this.project.music.name}</div>
                    <button class="timeline-btn" onclick="ReelStudio.removeMusic()">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
                <div class="prop-group">
                    <label class="prop-label">Volume</label>
                    <input type="range" class="prop-slider" min="0" max="1" step="0.1" value="${this.project.music.volume}" onchange="ReelStudio.setMusicVolume(this.value)">
                </div>
            </div>
        `;
    },
    
    // Set Music Volume
    setMusicVolume(volume) {
        if (this.project.music) {
            this.project.music.volume = parseFloat(volume);
        }
    },
    
    // Remove Music
    removeMusic() {
        this.project.music = null;
        this.loadMusicLibrary();
    },

    
    // Load Effects
    loadEffects() {
        const panel = document.getElementById('panelContent');
        const filters = [
            { name: 'None', filter: 'none' },
            { name: 'Vintage', filter: 'sepia(0.5) contrast(1.2)' },
            { name: 'B&W', filter: 'grayscale(1)' },
            { name: 'Vibrant', filter: 'saturate(1.5) contrast(1.1)' },
            { name: 'Cool', filter: 'hue-rotate(180deg)' },
            { name: 'Warm', filter: 'sepia(0.3) saturate(1.3)' },
            { name: 'Blur', filter: 'blur(3px)' },
            { name: 'Bright', filter: 'brightness(1.3)' }
        ];
        
        let html = '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;">';
        filters.forEach(f => {
            html += `
                <div class="filter-card" onclick="ReelStudio.applyFilter('${f.filter}')" style="background: #1a1a1a; border-radius: 8px; padding: 15px; cursor: pointer; text-align: center;">
                    <div style="width: 100%; height: 80px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 6px; margin-bottom: 8px; filter: ${f.filter};"></div>
                    <div style="font-size: 12px;">${f.name}</div>
                </div>
            `;
        });
        html += '</div>';
        panel.innerHTML = html;
    },
    
    // Apply Filter
    applyFilter(filter) {
        if (this.selectedLayer && this.selectedLayer.type === 'image') {
            this.selectedLayer.filter = filter;
            this.renderCanvas();
        } else {
            alert('Please select an image layer first');
        }
    },
    
    // Load Animations
    loadAnimations() {
        const panel = document.getElementById('panelContent');
        const animations = [
            { name: 'Zoom In', value: 'zoom' },
            { name: 'Fade In', value: 'fadeIn' },
            { name: 'Slide Left', value: 'slideLeft' },
            { name: 'Slide Right', value: 'slideRight' },
            { name: 'Slide Up', value: 'slideUp' },
            { name: 'Slide Down', value: 'slideDown' },
            { name: 'Rotate', value: 'rotate' },
            { name: 'Bounce', value: 'bounce' }
        ];
        
        let html = '<div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;">';
        animations.forEach(anim => {
            html += `
                <button class="canvas-btn" style="width: 100%; padding: 20px;" onclick="ReelStudio.applyAnimation('${anim.value}')">
                    <i class="fas fa-play-circle" style="margin-bottom: 5px;"></i>
                    <div style="font-size: 11px;">${anim.name}</div>
                </button>
            `;
        });
        html += '</div>';
        panel.innerHTML = html;
    },
    
    // Apply Animation
    applyAnimation(animation) {
        if (this.selectedLayer) {
            this.selectedLayer.animation = animation;
            alert(`Animation "${animation}" applied to layer`);
        } else {
            alert('Please select a layer first');
        }
    },

    
    // Load Settings
    loadSettings() {
        const panel = document.getElementById('panelContent');
        panel.innerHTML = `
            <div class="prop-group">
                <label class="prop-label">Project Name</label>
                <input type="text" class="prop-input" value="${this.project.name}" onchange="ReelStudio.updateProjectName(this.value)">
            </div>
            
            <div class="prop-group">
                <label class="prop-label">Duration (seconds)</label>
                <input type="number" class="prop-input" value="${this.project.duration}" min="5" max="60" onchange="ReelStudio.updateDuration(this.value)">
            </div>
            
            <div class="prop-group">
                <label class="prop-label">Resolution</label>
                <select class="prop-input" onchange="ReelStudio.updateResolution(this.value)">
                    <option value="1080x1920" selected>1080x1920 (Instagram/TikTok)</option>
                    <option value="1080x1080">1080x1080 (Square)</option>
                    <option value="1920x1080">1920x1080 (Landscape)</option>
                </select>
            </div>
            
            <div class="prop-group">
                <label class="prop-label">Frame Rate</label>
                <select class="prop-input" onchange="ReelStudio.updateFPS(this.value)">
                    <option value="24">24 FPS</option>
                    <option value="30" selected>30 FPS</option>
                    <option value="60">60 FPS</option>
                </select>
            </div>
            
            <div class="prop-group">
                <label class="prop-label">Background Color</label>
                <input type="color" class="prop-input" value="#000000" onchange="ReelStudio.updateBackground(this.value)">
            </div>
        `;
    },
    
    // Update Project Name
    updateProjectName(name) {
        this.project.name = name;
        document.getElementById('projectName').textContent = name;
    },
    
    // Update Duration
    updateDuration(duration) {
        this.project.duration = parseInt(duration);
    },
    
    // Update Resolution
    updateResolution(resolution) {
        const [width, height] = resolution.split('x').map(Number);
        this.project.width = width;
        this.project.height = height;
        this.renderCanvas();
    },
    
    // Update FPS
    updateFPS(fps) {
        this.project.fps = parseInt(fps);
    },
    
    // Update Background
    updateBackground(color) {
        document.getElementById('canvasStage').style.background = color;
    },

    
    // Render Canvas
    renderCanvas() {
        const stage = document.getElementById('canvasStage');
        stage.innerHTML = '';
        
        // Render all layers
        this.project.layers.forEach(layer => {
            const element = this.createLayerElement(layer);
            if (element) {
                stage.appendChild(element);
            }
        });
    },
    
    // Create Layer Element
    createLayerElement(layer) {
        const el = document.createElement('div');
        el.id = `layer-${layer.id}`;
        el.style.position = 'absolute';
        el.style.transform = `translate(-50%, -50%) rotate(${layer.rotation}deg)`;
        el.style.opacity = layer.opacity;
        el.style.cursor = 'pointer';
        el.onclick = () => this.selectLayer(layer.id);
        
        if (layer.type === 'image') {
            el.style.left = '50%';
            el.style.top = '50%';
            el.style.width = '100%';
            el.style.height = '100%';
            el.innerHTML = `<img src="${layer.url}" style="width: 100%; height: 100%; object-fit: cover; filter: ${layer.filter || 'none'};">`;
        }
        else if (layer.type === 'text') {
            el.style.left = '50%';
            el.style.top = layer.y + 'px';
            el.style.fontFamily = layer.font;
            el.style.fontSize = layer.size + 'px';
            el.style.color = layer.color;
            el.style.fontWeight = 'bold';
            el.style.textAlign = 'center';
            el.style.textShadow = '2px 2px 4px rgba(0,0,0,0.8)';
            el.style.padding = '10px 20px';
            el.textContent = layer.content;
        }
        else if (layer.type === 'shape') {
            el.style.left = layer.x + 'px';
            el.style.top = layer.y + 'px';
            el.style.width = layer.width + 'px';
            el.style.height = layer.height + 'px';
            el.style.background = layer.color;
            if (layer.shape === 'circle') {
                el.style.borderRadius = '50%';
            } else if (layer.shape === 'star') {
                el.innerHTML = '<i class="fas fa-star" style="font-size: 100px; color: ' + layer.color + ';"></i>';
                el.style.background = 'transparent';
            }
        }
        else if (layer.type === 'icon') {
            el.style.left = layer.x + 'px';
            el.style.top = layer.y + 'px';
            el.style.fontSize = layer.size + 'px';
            el.style.color = layer.color;
            el.innerHTML = `<i class="fas fa-${layer.icon}"></i>`;
        }
        
        return el;
    },
    
    // Select Layer
    selectLayer(layerId) {
        this.selectedLayer = this.project.layers.find(l => l.id === layerId);
        console.log('Selected layer:', this.selectedLayer);
        this.loadLayerProperties();
    },
    
    // Load Layer Properties
    loadLayerProperties() {
        if (!this.selectedLayer) return;
        
        const content = document.getElementById('propertiesContent');
        let html = `
            <div class="prop-group">
                <label class="prop-label">Layer: ${this.selectedLayer.type}</label>
            </div>
            
            <div class="prop-group">
                <label class="prop-label">Opacity</label>
                <input type="range" class="prop-slider" min="0" max="1" step="0.1" value="${this.selectedLayer.opacity}" onchange="ReelStudio.updateLayerProperty('opacity', this.value)">
            </div>
            
            <div class="prop-group">
                <label class="prop-label">Rotation</label>
                <input type="range" class="prop-slider" min="0" max="360" value="${this.selectedLayer.rotation}" onchange="ReelStudio.updateLayerProperty('rotation', this.value)">
            </div>
            
            <div class="prop-group">
                <label class="prop-label">Start Time (seconds)</label>
                <input type="number" class="prop-input" value="${this.selectedLayer.startTime}" min="0" onchange="ReelStudio.updateLayerProperty('startTime', this.value)">
            </div>
            
            <div class="prop-group">
                <label class="prop-label">Duration (seconds)</label>
                <input type="number" class="prop-input" value="${this.selectedLayer.duration}" min="1" onchange="ReelStudio.updateLayerProperty('duration', this.value)">
            </div>
            
            <button class="canvas-btn" style="width: 100%; background: #ff4444; margin-top: 20px;" onclick="ReelStudio.deleteLayer()">
                <i class="fas fa-trash"></i> Delete Layer
            </button>
        `;
        
        content.innerHTML = html;
    },
    
    // Update Layer Property
    updateLayerProperty(property, value) {
        if (this.selectedLayer) {
            this.selectedLayer[property] = parseFloat(value) || value;
            this.renderCanvas();
            this.renderTimeline();
        }
    },
    
    // Delete Layer
    deleteLayer() {
        if (!this.selectedLayer) return;
        
        if (confirm('Delete this layer?')) {
            this.project.layers = this.project.layers.filter(l => l.id !== this.selectedLayer.id);
            this.project.timeline = this.project.timeline.filter(l => l.id !== this.selectedLayer.id);
            this.selectedLayer = null;
            this.renderCanvas();
            this.renderTimeline();
            document.getElementById('propertiesContent').innerHTML = '<div style="color: #888; text-align: center; padding: 40px 20px;">Select a layer to edit properties</div>';
        }
    },

    
    // Render Timeline
    renderTimeline() {
        const tracks = document.getElementById('timelineTracks');
        tracks.innerHTML = '';
        
        if (this.project.timeline.length === 0) {
            tracks.innerHTML = '<div style="color: #888; text-align: center; padding: 40px;">Add images or elements to see timeline</div>';
            return;
        }
        
        const track = document.createElement('div');
        track.className = 'timeline-track';
        
        this.project.timeline.forEach(layer => {
            const clip = document.createElement('div');
            clip.className = 'timeline-clip';
            clip.style.width = (layer.duration * 50) + 'px';
            clip.onclick = () => this.selectLayer(layer.id);
            
            let thumbnail = '';
            if (layer.type === 'image') {
                thumbnail = `<img src="${layer.url}" class="clip-thumbnail">`;
            } else if (layer.type === 'text') {
                thumbnail = '<i class="fas fa-font" style="font-size: 20px;"></i>';
            } else {
                thumbnail = '<i class="fas fa-layer-group" style="font-size: 20px;"></i>';
            }
            
            clip.innerHTML = `
                ${thumbnail}
                <div class="clip-info">
                    <div class="clip-name">${layer.name || layer.type}</div>
                    <div class="clip-duration">${layer.duration}s</div>
                </div>
            `;
            
            track.appendChild(clip);
        });
        
        tracks.appendChild(track);
    },
    
    // Handle Canvas Click
    handleCanvasClick(e) {
        // Click handling logic
    },
    
    // Handle Keyboard
    handleKeyboard(e) {
        // Ctrl+Z - Undo
        if (e.ctrlKey && e.key === 'z') {
            this.undoAction();
        }
        // Ctrl+Y - Redo
        if (e.ctrlKey && e.key === 'y') {
            this.redoAction();
        }
        // Delete - Delete layer
        if (e.key === 'Delete' && this.selectedLayer) {
            this.deleteLayer();
        }
    },
    
    // Switch Property Tab
    switchPropertyTab(tab) {
        document.querySelectorAll('.prop-tab').forEach(t => t.classList.remove('active'));
        document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
        
        if (tab === 'export') {
            this.loadExportOptions();
        }
    },
    
    // Load Export Options
    loadExportOptions() {
        const content = document.getElementById('propertiesContent');
        content.innerHTML = `
            <div class="prop-group">
                <label class="prop-label">Export Quality</label>
                <select class="prop-input" id="exportQuality">
                    <option value="high">High Quality (Recommended)</option>
                    <option value="medium">Medium Quality</option>
                    <option value="low">Low Quality (Faster)</option>
                </select>
            </div>
            
            <div class="prop-group">
                <label class="prop-label">Format</label>
                <select class="prop-input" id="exportFormat">
                    <option value="mp4">MP4 (Recommended)</option>
                    <option value="webm">WebM</option>
                </select>
            </div>
            
            <div class="prop-group">
                <label class="prop-label">Add Watermark</label>
                <input type="checkbox" id="addWatermark" checked>
                <label for="addWatermark" style="margin-left: 10px;">VibeMall Logo</label>
            </div>
            
            <div class="prop-group">
                <label class="prop-label">Add End Screen</label>
                <input type="checkbox" id="addEndScreen" checked>
                <label for="addEndScreen" style="margin-left: 10px;">Branded End Screen</label>
            </div>
            
            <button class="canvas-btn primary" style="width: 100%; margin-top: 20px;" onclick="ReelStudio.startExport()">
                <i class="fas fa-download"></i> Export Video
            </button>
        `;
    },

    
    // Start Export
    startExport() {
        alert('🎬 Export functionality will generate video using backend!\n\nProject data will be sent to server for video generation with MoviePy.');
        this.exportToBackend();
    },
    
    // Export to Backend
    async exportToBackend() {
        // Check if there are images
        const imageCount = this.project.layers.filter(l => l.type === 'image').length;
        if (imageCount === 0) {
            alert('❌ Please add at least one image before exporting!');
            return;
        }
        
        const projectData = {
            name: this.project.name,
            width: this.project.width,
            height: this.project.height,
            duration: this.project.duration,
            fps: this.project.fps,
            layers: this.project.layers,
            music: this.project.music,
            settings: {
                quality: document.getElementById('exportQuality')?.value || 'high',
                format: document.getElementById('exportFormat')?.value || 'mp4',
                watermark: document.getElementById('addWatermark')?.checked || false,
                endScreen: document.getElementById('addEndScreen')?.checked || false
            }
        };
        
        console.log('Exporting project:', projectData);
        
        // Show loading
        const exportBtn = event.target;
        const originalText = exportBtn.innerHTML;
        exportBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Exporting...';
        exportBtn.disabled = true;
        
        // Send to backend
        try {
            const response = await fetch('/admin-panel/reels/studio/export/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(projectData)
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                alert('✅ ' + result.message);
                window.location.href = '/admin-panel/reels/';
            } else {
                alert('❌ Export failed: ' + (result.error || 'Unknown error'));
                exportBtn.innerHTML = originalText;
                exportBtn.disabled = false;
            }
        } catch (error) {
            console.error('Export error:', error);
            alert('❌ Export failed: ' + error.message);
            exportBtn.innerHTML = originalText;
            exportBtn.disabled = false;
        }
    },
    
    // Get CSRF Token
    getCSRFToken() {
        // Try multiple methods to get CSRF token
        let token = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        if (!token) {
            token = document.querySelector('meta[name="csrf-token"]')?.content;
        }
        if (!token) {
            token = this.getCookie('csrftoken');
        }
        return token || '';
    },
    
    // Get Cookie
    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    },
    
    // Save Project
    saveProject() {
        const projectData = JSON.stringify(this.project);
        localStorage.setItem('reelStudioProject', projectData);
        alert('✅ Project saved locally!');
    },
    
    // Load Project
    loadProject() {
        const projectData = localStorage.getItem('reelStudioProject');
        if (projectData) {
            this.project = JSON.parse(projectData);
            this.renderCanvas();
            this.renderTimeline();
            alert('✅ Project loaded!');
        }
    },
    
    // Undo Action
    undoAction() {
        console.log('Undo');
        // Undo logic here
    },
    
    // Redo Action
    redoAction() {
        console.log('Redo');
        // Redo logic here
    },
    
    // Play Preview
    playPreview() {
        console.log('Play preview');
        this.isPlaying = true;
        // Preview animation logic
    },
    
    // Stop Preview
    stopPreview() {
        console.log('Stop preview');
        this.isPlaying = false;
    },
    
    // Zoom Timeline
    zoomTimeline(direction) {
        console.log('Zoom timeline:', direction);
    }
};

// Export Video Function (Global)
function exportVideo() {
    ReelStudio.startExport();
}

// Save Project Function (Global)
function saveProject() {
    ReelStudio.saveProject();
}

// Undo/Redo Functions (Global)
function undoAction() {
    ReelStudio.undoAction();
}

function redoAction() {
    ReelStudio.redoAction();
}

// Preview Functions (Global)
function playPreview() {
    ReelStudio.playPreview();
}

function stopPreview() {
    ReelStudio.stopPreview();
}

function zoomTimeline(direction) {
    ReelStudio.zoomTimeline(direction);
}
