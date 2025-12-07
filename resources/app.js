(function() {
    'use strict';
    
    const state = {
        isLoggedIn: false,
        isDark: localStorage.getItem('theme') !== 'light', // 默认为深色，除非明确设置为 light
        sidebarOpen: true,
        activeTab: 'info',
        graphData: { nodes: [], links: [] },
        currentSessionId: null, // 新增：当前加载的会话ID
        selectedNode: null,
        hoverNode: null,
        highlightNodes: new Set(),
        highlightLinks: new Set(),
        debugResult: null,
        showLabels: true,
        Graph: null,
        // 监控状态
        ws: null,
        logPaused: false,
        logLevel: 'ALL',
        // 存储从 WebSocket 收到的原始日志数据
        logCache: []
    };
    
    const el = {
        loginScreen: document.getElementById('login-screen'),
        loginKey: document.getElementById('login-key'),
        loginBtn: document.getElementById('login-btn'),
        loginError: document.getElementById('login-error'),
        mainApp: document.getElementById('main-app'),
        themeToggle: document.getElementById('theme-toggle'),
        logoutBtn: document.getElementById('logout-btn'),
        sidebarToggle: document.getElementById('sidebar-toggle-btn'),
        sidebar: document.getElementById('sidebar'),
        searchInput: document.getElementById('search-input'),
        sessionSelector: document.getElementById('session-selector'),
        tabInfo: document.getElementById('tab-info'),
        tabDebug: document.getElementById('tab-debug'),
        tabMonitor: document.getElementById('tab-monitor'),
        nodeInfoEmpty: document.getElementById('node-info-empty'),
        nodeInfoDetail: document.getElementById('node-info-detail'),
        debugQuery: document.getElementById('debug-query'),
        debugSession: document.getElementById('debug-session'), // 新增
        debugPersona: document.getElementById('debug-persona'), // 新增
        debugSearchBtn: document.getElementById('debug-search-btn'),
        debugLoader: document.getElementById('debug-loader'),
        debugText: document.getElementById('debug-text'),
        debugResult: document.getElementById('debug-result'),
        debugStats: document.getElementById('debug-stats'),
        debugJson: document.getElementById('debug-json'),
        visualizeBtn: document.getElementById('visualize-btn'),
        graphContainer: document.getElementById('graph-container'),
        nodeCount: document.getElementById('node-count'),
        edgeCount: document.getElementById('edge-count'),
        showLabels: document.getElementById('show-labels'),
        reloadBtn: document.getElementById('reload-btn'),
        fitViewBtn: document.getElementById('fit-view-btn'),
        tooltip: document.getElementById('tooltip'),
        // 监控面板元素
        monitorLogs: document.getElementById('monitor-logs'),
        monitorTasks: document.getElementById('monitor-tasks'),
        monitorMessages: document.getElementById('monitor-messages'),
        logLevelFilter: document.getElementById('log-level-filter'),
        logPauseToggle: document.getElementById('log-pause-toggle'),
        logClear: document.getElementById('log-clear'),
        toolsBtn: document.getElementById('tools-btn'),
        linkModeBtn: document.getElementById('link-mode-btn'),
        modalOverlay: document.getElementById('modal-overlay'),
        modalBox: document.getElementById('modal-box'),
        modalTitle: document.getElementById('modal-title'),
        modalContent: document.getElementById('modal-content'),
        modalCloseBtn: document.getElementById('modal-close-btn')
    };
    
    function getAuthHeaders() {
        const token = localStorage.getItem('session_token');
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    }
    
    async function checkSession() {
        let token = localStorage.getItem('session_token');
        if (!token) {
            const cookies = document.cookie.split(';');
            const sessionCookie = cookies.find(c => c.trim().startsWith('session_token='));
            if (sessionCookie) {
                token = sessionCookie.split('=')[1].trim();
                localStorage.setItem('session_token', token);
            }
        }
        if (token) {
            try {
                // Use a valid, lightweight endpoint for session checking
                const res = await fetch('/api/contexts', { headers: getAuthHeaders() });
                if (res.ok) {
                    state.isLoggedIn = true;
                    showMainApp();
                    return;
                }
            } catch (e) {
                console.error('会话验证失败:', e);
            }
            localStorage.removeItem('session_token');
            document.cookie = 'session_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
        }
    }
    
    async function login() {
        const key = el.loginKey.value.trim();
        if (!key) return;
        
        try {
            const res = await fetch('/api/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key })
            });
            
            if (res.ok) {
                const data = await res.json();
                if (data.token) localStorage.setItem('session_token', data.token);
                state.isLoggedIn = true;
                el.loginError.textContent = '';
                showMainApp();
            } else {
                el.loginError.textContent = '访问密钥无效';
            }
        } catch (e) {
            el.loginError.textContent = '连接错误: ' + e.message;
        }
    }

    function openModal(title, content) {
        el.modalTitle.textContent = title;
        el.modalContent.innerHTML = content;
        el.modalOverlay.classList.remove('hidden');
    }

    function closeModal() {
        el.modalOverlay.classList.add('hidden');
        el.modalContent.innerHTML = '';
    }

    function showBatchOperationsModal() {
        const content = `
            <p style="font-size: 0.875rem; color: #999; margin-bottom: 1.5rem;">选择一个预设的维护任务来清理当前图谱。</p>
            <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                <button class="btn btn-secondary" data-task="delete_isolated_entities">删除孤立实体</button>
                <button class="btn btn-secondary" data-task="delete_old_messages" data-days="90">删除90天前的原始消息</button>
            </div>
            <div id="batch-op-status" style="margin-top: 1rem; font-size: 0.75rem; color: #666;"></div>
        `;
        openModal('高级工具', content);
        lucide.createIcons();

        document.querySelectorAll('#modal-content .btn[data-task]').forEach(button => {
            button.addEventListener('click', async (e) => {
                const taskName = e.currentTarget.dataset.task;
                const days = e.currentTarget.dataset.days;
                const statusEl = document.getElementById('batch-op-status');
                
                statusEl.textContent = `正在执行: ${taskName}...`;
                
                try {
                    const params = days ? { days: parseInt(days) } : {};
                    const res = await fetch('/api/batch-delete', {
                        method: 'POST',
                        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
                        body: JSON.stringify({ task_name: taskName, params: params })
                    });

                    if (!res.ok) throw new Error(`服务器错误: ${res.statusText}`);
                    
                    const result = await res.json();
                    statusEl.textContent = `成功！删除了 ${result.deleted_count} 个节点。图谱将自动刷新。`;

                    // 等待一会再刷新，让用户看到成功信息
                    setTimeout(() => {
                        closeModal();
                        el.reloadBtn.click(); // 触发刷新
                    }, 2000);

                } catch (err) {
                    statusEl.textContent = `错误: ${err.message}`;
                }
            });
        });
    }

    function showLinkEntityModal() {
        if (!state.selectedNode || state.selectedNode.type !== 'Entity') {
            alert('请先选择一个实体节点。');
            return;
        }
        
        const entityName = state.selectedNode.name;
        const content = `
            <p style="font-size: 0.875rem; color: #999; margin-bottom: 1.5rem;">将实体 <strong>${entityName}</strong> 关联到当前会话。</p>
            <div style="margin-bottom: 1rem;">
                <label style="display: block; font-size: 0.75rem; font-weight: 600; margin-bottom: 0.5rem;">目标会话 ID</label>
                <input type="text" id="link-session-id" value="${state.currentSessionId !== 'global' ? state.currentSessionId : ''}" style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 0.25rem; background: transparent; color: inherit;">
            </div>
            <button id="confirm-link-btn" class="btn btn-primary">确认关联</button>
            <div id="link-status" style="margin-top: 1rem; font-size: 0.75rem; color: #666;"></div>
        `;
        openModal('关联实体', content);
        
        document.getElementById('confirm-link-btn').addEventListener('click', async () => {
            const sessionId = document.getElementById('link-session-id').value.trim();
            const statusEl = document.getElementById('link-status');
            
            if (!sessionId) {
                statusEl.textContent = '请输入会话 ID。';
                return;
            }
            
            statusEl.textContent = '正在关联...';
            
            try {
                const res = await fetch('/api/link', {
                    method: 'POST',
                    headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId, entity_name: entityName })
                });
                
                if (!res.ok) throw new Error(`服务器错误: ${res.statusText}`);
                
                statusEl.textContent = '关联成功！';
                setTimeout(() => {
                    closeModal();
                    if (state.currentSessionId === sessionId) {
                        el.reloadBtn.click();
                    }
                }, 1500);
            } catch (err) {
                statusEl.textContent = `错误: ${err.message}`;
            }
        });
    }



    function logout() {
        state.isLoggedIn = false;
        localStorage.removeItem('session_token');
        document.cookie = 'session_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;';
        if (state.Graph) {
            state.Graph._destructor();
            state.Graph = null;
        }
        el.mainApp.classList.add('hidden');
        el.loginScreen.classList.remove('hidden');
    }
    
    function showMainApp() {
        el.loginScreen.classList.add('hidden');
        el.mainApp.classList.remove('hidden');
        // Initialize the app logic (fetch contexts, then load graph)
        initApp();
        // 连接 WebSocket
        connectWebSocket();
    }
    
    function toggleTheme() {
        state.isDark = !state.isDark;
        localStorage.setItem('theme', state.isDark ? 'dark' : 'light');
        document.body.classList.toggle('dark', state.isDark);
        
        el.themeToggle.innerHTML = `<i data-lucide="${state.isDark ? 'sun' : 'moon'}" style="width: 1rem; height: 1rem;"></i>`;
        lucide.createIcons();
        
        if (state.Graph) {
            const bgColor = state.isDark ? '#080808' : '#f2f2f2';
            state.Graph.backgroundColor(bgColor);
            
            // 强制刷新画布对象以更新颜色
            // ForceGraph 的访问器函数会在内部调用时使用当前的 state.isDark
            // 重新设置访问器会触发内部更新
            state.Graph.nodeColor(state.Graph.nodeColor());
            state.Graph.linkColor(state.Graph.linkColor());
            state.Graph.nodeCanvasObject(state.Graph.nodeCanvasObject()); // 触发自定义绘制更新
        }
    }
    
    function toggleSidebar() {
        state.sidebarOpen = !state.sidebarOpen;
        if (state.sidebarOpen) {
            el.sidebar.classList.remove('closed');
            el.graphContainer.classList.remove('full');
        } else {
            el.sidebar.classList.add('closed');
            el.graphContainer.classList.add('full');
        }
        
        setTimeout(() => {
            if (state.Graph) {
                const width = el.graphContainer.clientWidth;
                const height = el.graphContainer.clientHeight;
                state.Graph.width(width);
                state.Graph.height(height);
            }
        }, 310);
    }
    
    function switchTab(tabName) {
        state.activeTab = tabName;
        document.querySelectorAll('.tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });
        el.tabInfo.classList.toggle('hidden', tabName !== 'info');
        el.tabDebug.classList.toggle('hidden', tabName !== 'debug');
        el.tabMonitor.classList.toggle('hidden', tabName !== 'monitor');
    }
    
    function initGraph() {
        if (state.Graph) return;
        el.graphContainer.innerHTML = '';
        
        const getNodeColor = (node) => {
            // 非高亮状态下的淡化处理
            if (state.highlightNodes.size > 0 && !state.highlightNodes.has(node.id)) {
                return state.isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)';
            }
            // 选中节点：黑白强对比
            if (node === state.selectedNode) return state.isDark ? '#fff' : '#000';
            
            // 基于类型的低饱和度高级配色方案 (Morandi-inspired)
            const type = (node.type || '').toLowerCase();
            
            if (type.includes('concept') || type.includes('memory')) return '#818cf8'; // Indigo
            if (type.includes('action') || type.includes('event')) return '#34d399'; // Emerald
            if (type.includes('persona') || type.includes('user')) return '#60a5fa'; // Blue
            if (type.includes('loc') || type.includes('place')) return '#f472b6'; // Pink
            if (type.includes('time') || type.includes('date')) return '#fcd34d'; // Amber (Muted)
            
            // 默认/其他类型：中性冷灰
            return '#9ca3af';
        };
        
        const getLinkColor = (link) => {
            const isDimmed = state.highlightLinks.size > 0 && !state.highlightLinks.has(link);
            
            if (isDimmed) {
                return state.isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)';
            }
            // 提高默认可见度
            return state.isDark ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.3)';
        };
        
        const getTextColor = () => state.isDark ? 'rgba(255,255,255,0.8)' : 'rgba(0,0,0,0.8)';
        
        state.Graph = ForceGraph()(el.graphContainer)
            .backgroundColor(state.isDark ? '#080808' : '#f2f2f2')
            .nodeLabel('name')
            .nodeColor(getNodeColor)
            .nodeVal(node => (node.importance || 0.5) * 5)
            .nodeRelSize(4)
            .linkColor(getLinkColor)
            .linkWidth(link => state.highlightLinks.has(link) ? 2.5 : 1)
            .linkDirectionalParticles(link => state.highlightLinks.has(link) ? 3 : 0)
            .linkDirectionalParticleWidth(3)
            .onNodeClick(node => {
                state.selectedNode = node;
                highlightNetwork(node);
                focusNode(node);
                switchTab('info');
                // 自动展开侧边栏（如果关闭）
                if (!state.sidebarOpen) toggleSidebar();
                renderNodeInfo();
            })
            .onNodeHover(node => {
                state.hoverNode = node;
                el.graphContainer.style.cursor = node ? 'pointer' : null;
                if (node) {
                    el.tooltip.textContent = `${node.name} (${node.type})`;
                    el.tooltip.classList.remove('hidden');
                } else {
                    el.tooltip.classList.add('hidden');
                }
            })
            .onBackgroundClick(() => {
                state.selectedNode = null;
                state.highlightNodes.clear();
                state.highlightLinks.clear();
                state.Graph.nodeColor(state.Graph.nodeColor());
                state.Graph.linkColor(state.Graph.linkColor());
                state.Graph.linkDirectionalParticles(0);
                renderNodeInfo();
            })
            .nodeCanvasObject((node, ctx, globalScale) => {
                const r = Math.sqrt(Math.max(0, (node.importance || 0.5) * 5)) * 4;
                const isSelected = node === state.selectedNode;
                const isHighlighted = state.highlightNodes.has(node.id);
                const isDimmed = state.highlightNodes.size > 0 && !isHighlighted;
                
                ctx.beginPath();
                ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
                ctx.fillStyle = isDimmed ? (state.isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)') : getNodeColor(node);
                ctx.fill();
                
                // 绘制选中光环
                if (isSelected) {
                    // 浅色模式下选中光环改为深色，深色模式下为白色
                    ctx.strokeStyle = state.isDark ? '#fff' : '#333';
                    ctx.lineWidth = 2 / globalScale;
                    ctx.stroke();
                    
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, r * 1.5, 0, 2 * Math.PI, false);
                    // 外圈光环
                    ctx.strokeStyle = state.isDark ? 'rgba(255,255,255,0.3)' : 'rgba(0,0,0,0.1)';
                    ctx.lineWidth = 1 / globalScale;
                    ctx.stroke();
                }
                
                // 绘制标签
                if (state.showLabels || isSelected || isHighlighted) {
                    const label = node.name;
                    const fontSize = (isSelected ? 14 : 10) / globalScale;
                    ctx.font = `${isSelected ? 'bold' : ''} ${fontSize}px 'Inter', sans-serif`;
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'top';
                    
                    // 动态获取当前主题下的文本颜色
                    // 必须实时判断，不能缓存
                    const currentTextColor = state.isDark ? 'rgba(255,255,255,0.8)' : 'rgba(0,0,0,0.8)';
                    const dimmedColor = state.isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.2)';
                    
                    ctx.fillStyle = isDimmed ? dimmedColor : currentTextColor;
                    
                    // 绘制文字背景以提高可读性
                    if (isSelected) {
                        const textWidth = ctx.measureText(label).width;
                        const bgHeight = fontSize * 1.2;
                        ctx.fillStyle = state.isDark ? 'rgba(0,0,0,0.7)' : 'rgba(255,255,255,0.8)';
                        ctx.fillRect(node.x - textWidth/2 - 2, node.y + r + 2, textWidth + 4, bgHeight);
                        ctx.fillStyle = isDimmed ? dimmedColor : currentTextColor; // 恢复文字颜色
                    }
                    
                    ctx.fillText(label, node.x, node.y + r + 2);
                }
            })
            .graphData(state.graphData);
        
        el.graphContainer.addEventListener('mousemove', (e) => {
            el.tooltip.style.left = e.clientX + 'px';
            el.tooltip.style.top = e.clientY + 'px';
        });

        if (!window._resizeListenerAdded) {
            window.addEventListener('resize', () => {
                if (state.Graph) {
                    state.Graph.width(el.graphContainer.clientWidth);
                    state.Graph.height(el.graphContainer.clientHeight);
                }
            });
            window._resizeListenerAdded = true;
        }
        
        // Data loading is now handled by initApp and loadGraphData
    }
    
    async function initApp() {
        // 1. 立即初始化空的图谱画布
        initGraph();

        // 2. 异步、非阻塞地获取会话列表并填充下拉菜单
        try {
            const res = await fetch('/api/contexts', { headers: getAuthHeaders() });
            if (!res.ok) {
                console.error('无法获取会话列表用于填充下拉菜单。');
            } else {
                const contexts = await res.json();
                console.log('获取到的会话上下文:', contexts);

                el.sessionSelector.innerHTML = '<option value="global">全局视图</option>';
                if (contexts && contexts.length > 0) {
                    contexts.forEach(ctx => {
                        const option = document.createElement('option');
                        option.value = ctx.session_id;
                        // 截断过长的 ID 以优化显示
                        const displayName = ctx.session_id.length > 30 ? `...${ctx.session_id.slice(-27)}` : ctx.session_id;
                        option.textContent = displayName;
                        el.sessionSelector.appendChild(option);
                    });
                } else {
                    console.log('No contexts found to load.');
                }
            }
        } catch (e) {
            console.error("填充会话下拉菜单时出错:", e);
        }

        // 3. 无论会话列表是否获取成功，都默认加载全局视图作为初始状态
        console.log("默认加载全局视图...");
        el.sessionSelector.value = 'global';
        await loadGraphData('global');
    }
    
    async function loadGraphData(sessionId) {
        // sessionId 可以是一个字符串 ID 或 "global"
        console.log(`开始加载图谱数据，视图: ${sessionId}`); // 增加诊断日志
        state.currentSessionId = sessionId;
        
        const url = (sessionId && sessionId !== 'global')
            ? `/api/graph?session_id=${encodeURIComponent(sessionId)}`
            : '/api/graph';

        try {
            const res = await fetch(url, { headers: getAuthHeaders() });
            if (!res.ok) {
                if (res.status === 401) {
                    console.error('认证失败，重新登录');
                    logout();
                }
                throw new Error(`Failed to load graph data for view: ${sessionId}`);
            }
            const data = await res.json();
            
            // 检查数据是否有效
            if (!data || data === null) {
                console.error('收到空的图谱数据');
                state.graphData = { nodes: [], links: [] };
                updateStats();
                return;
            }
            
            // 过滤掉无效的节点和边
            const validNodes = (data.nodes || []).filter(n => n && n.id);
            const nodeIds = new Set(validNodes.map(n => n.id));
            
            // 只保留source和target都存在的边
            const validEdges = (data.edges || []).filter(e =>
                e && e.source && e.target && nodeIds.has(e.source) && nodeIds.has(e.target)
            );
            
            console.log(`有效节点: ${validNodes.length}, 有效边: ${validEdges.length}`);
            
            // The backend returns 'edges' with 'source'/'target', force-graph uses 'links'
            state.graphData = {
                nodes: validNodes,
                links: validEdges
            };
    
            updateStats();
            if (state.Graph) {
                state.Graph.graphData(state.graphData);
                setTimeout(() => state.Graph.zoomToFit(400), 200);
            }
    
        } catch (e) {
            console.error('加载图谱数据错误:', e);
        }
    }
    
    function updateStats() {
        el.nodeCount.textContent = state.graphData.nodes.length;
        el.edgeCount.textContent = state.graphData.links.length;
    }
    
    function highlightNetwork(node) {
        state.highlightNodes.clear();
        state.highlightLinks.clear();
        
        if (!node) return;
        
        state.highlightNodes.add(node.id);
        state.graphData.links.forEach(link => {
            const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;
            
            if (sourceId === node.id) {
                state.highlightLinks.add(link);
                state.highlightNodes.add(targetId);
            }
            if (targetId === node.id) {
                state.highlightLinks.add(link);
                state.highlightNodes.add(sourceId);
            }
        });
        
        state.Graph.nodeColor(state.Graph.nodeColor());
        state.Graph.linkColor(state.Graph.linkColor());
        state.Graph.linkWidth(state.Graph.linkWidth());
        state.Graph.linkDirectionalParticles(link => state.highlightLinks.has(link) ? 2 : 0);
    }
    
    function focusNode(node) {
        if (!state.Graph || !node) return;
        state.Graph.centerAt(node.x, node.y, 1000);
        state.Graph.zoom(3, 1000);
    }
    
    function renderNodeInfo() {
        if (!state.selectedNode) {
            el.nodeInfoEmpty.classList.remove('hidden');
            el.nodeInfoDetail.classList.add('hidden');
            return;
        }
        
        el.nodeInfoEmpty.classList.add('hidden');
        el.nodeInfoDetail.classList.remove('hidden');
        
        const node = state.selectedNode;
        el.nodeInfoDetail.innerHTML = `
            <div style="margin-bottom: 1.5rem;">
                <h3 id="node-name" style="font-size: 1rem; font-weight: 600; margin-bottom: 0.5rem;">${node.name}</h3>
                <div style="display: flex; gap: 0.5rem; font-size: 0.625rem; font-family: 'Courier New', monospace; color: #666;">
                    <span id="node-type" style="padding: 0.25rem 0.5rem; background: rgba(0,0,0,0.05); border-radius: 0.25rem;">${node.type}</span>
                    <span id="node-id" style="padding: 0.25rem 0.5rem; background: rgba(0,0,0,0.05); border-radius: 0.25rem;">${node.id}</span>
                </div>
            </div>
            
            <div style="margin-bottom: 1.5rem;">
                <h4 style="font-size: 0.625rem; font-weight: 700; color: #666; margin-bottom: 0.75rem; letter-spacing: 0.1em; text-transform: uppercase;">Properties</h4>
                <div id="node-properties"></div>
            </div>
            
            <div style="margin-bottom: 1.5rem;">
                <h4 style="font-size: 0.625rem; font-weight: 700; color: #666; margin-bottom: 0.75rem; letter-spacing: 0.1em; text-transform: uppercase;">Observations</h4>
                <div id="node-observations"></div>
            </div>
            
            <div>
                <h4 style="font-size: 0.625rem; font-weight: 700; color: #666; margin-bottom: 0.75rem; letter-spacing: 0.1em; text-transform: uppercase;">Connected Nodes</h4>
                <div id="node-neighbors"></div>
            </div>
        `;
        
        const propsContainer = document.getElementById('node-properties');
        if (node.properties && Object.keys(node.properties).length > 0) {
            Object.entries(node.properties).forEach(([key, value]) => {
                const div = document.createElement('div');
                div.style.cssText = 'margin-bottom: 0.5rem; font-size: 0.75rem;';
                div.innerHTML = `<span style="color: #999;">${key}:</span> <span>${JSON.stringify(value)}</span>`;
                propsContainer.appendChild(div);
            });
        } else {
            propsContainer.innerHTML = '<div style="color: #999; font-size: 0.75rem;">No properties</div>';
        }
        
        const obsContainer = document.getElementById('node-observations');
        if (node.observations && node.observations.length > 0) {
            node.observations.forEach(obs => {
                const div = document.createElement('div');
                div.style.cssText = 'margin-bottom: 0.5rem; padding: 0.5rem; background: rgba(0,0,0,0.03); border-radius: 0.375rem; font-size: 0.75rem;';
                div.textContent = obs;
                obsContainer.appendChild(div);
            });
        } else {
            obsContainer.innerHTML = '<div style="color: #999; font-size: 0.75rem;">No observations</div>';
        }
        
        const neighbors = state.graphData.links.filter(link => {
            const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;
            return sourceId === node.id || targetId === node.id;
        });
        
        const neighborsContainer = document.getElementById('node-neighbors');
        if (neighbors.length > 0) {
            neighbors.forEach(link => {
                const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
                const targetId = typeof link.target === 'object' ? link.target.id : link.target;
                const otherId = sourceId === node.id ? targetId : sourceId;
                const otherNode = state.graphData.nodes.find(n => n.id === otherId);
                if (otherNode) {
                    const div = document.createElement('div');
                    div.style.cssText = 'margin-bottom: 0.5rem; padding: 0.5rem; background: rgba(0,0,0,0.03); border-radius: 0.375rem; cursor: pointer; transition: background 0.2s; font-size: 0.75rem;';
                    div.innerHTML = `<span style="font-weight: 500;">${otherNode.name}</span> <span style="color: #999; font-size: 0.625rem;">(${link.relation})</span>`;
                    div.addEventListener('mouseenter', () => div.style.background = 'rgba(0,0,0,0.06)');
                    div.addEventListener('mouseleave', () => div.style.background = 'rgba(0,0,0,0.03)');
                    div.addEventListener('click', () => {
                        state.selectedNode = otherNode;
                        highlightNetwork(otherNode);
                        focusNode(otherNode);
                        renderNodeInfo();
                    });
                    neighborsContainer.appendChild(div);
                }
            });
        } else {
            neighborsContainer.innerHTML = '<div style="color: #999; font-size: 0.75rem;">No connections</div>';
        }
    }
    
    function performSearch(query) {
        if (!query.trim()) {
            state.highlightNodes.clear();
            state.highlightLinks.clear();
            state.Graph.nodeColor(state.Graph.nodeColor());
            state.Graph.linkColor(state.Graph.linkColor());
            state.Graph.linkDirectionalParticles(0);
            return;
        }
        
        const lowerQuery = query.toLowerCase();
        const matchedNodes = state.graphData.nodes.filter(node =>
            node.name.toLowerCase().includes(lowerQuery) ||
            node.type.toLowerCase().includes(lowerQuery) ||
            node.id.toLowerCase().includes(lowerQuery)
        );
        
        if (matchedNodes.length > 0) {
            state.highlightNodes.clear();
            state.highlightLinks.clear();
            matchedNodes.forEach(node => state.highlightNodes.add(node.id));
            state.Graph.nodeColor(state.Graph.nodeColor());
            state.Graph.linkColor(state.Graph.linkColor());
            
            if (matchedNodes.length === 1) {
                state.selectedNode = matchedNodes[0];
                focusNode(matchedNodes[0]);
                renderNodeInfo();
            }
        }
    }
    
    async function performDebugSearch() {
        const query = el.debugQuery.value.trim();
        if (!query) return;

        // Always use the currently loaded session ID for debugging
        const sid = state.currentSessionId;
        if (!sid) {
            alert("Please load a session context first.");
            return;
        }
        
        // 构建查询参数
        let url = `/api/debug_search?q=${encodeURIComponent(query)}&session_id=${encodeURIComponent(sid)}`;
        
        el.debugLoader.classList.remove('hidden');
        el.debugText.textContent = '';
        el.debugResult.classList.add('hidden');
        
        try {
            const res = await fetch(url, {
                headers: getAuthHeaders()
            });
            
            if (!res.ok) throw new Error('搜索失败: ' + res.statusText);
            const result = await res.json();
            
            state.debugResult = result;
            el.debugStats.textContent = `Nodes: ${result.nodes?.length || 0} | Edges: ${result.edges?.length || 0}`;
            el.debugJson.textContent = JSON.stringify(result, null, 2);
            
            el.debugLoader.classList.add('hidden');
            el.debugText.textContent = '搜索';
            el.debugResult.classList.remove('hidden');
            el.visualizeBtn.disabled = !result.nodes || result.nodes.length === 0;
        } catch (e) {
            el.debugLoader.classList.add('hidden');
            el.debugText.textContent = '搜索';
            el.debugStats.textContent = '错误: ' + e.message;
            el.debugResult.classList.remove('hidden');
        }
    }
    
    function visualizeDebugResult() {
        if (!state.debugResult || !state.debugResult.nodes) return;
        
        const debugNodes = state.debugResult.nodes.map(n => ({
            id: n.id || n.name,
            name: n.name || n.id,
            type: n.type || 'debug',
            group: 'debug',
            importance: n.importance || 0.7,
            properties: n.properties || {},
            observations: n.observations || []
        }));
        
        const debugLinks = (state.debugResult.edges || []).map(e => ({
            source: e.source,
            target: e.target,
            relation: e.relation || 'debug_link',
            weight: e.weight || 1
        }));
        
        state.graphData.nodes = debugNodes;
        state.graphData.links = debugLinks;
        state.Graph.graphData(state.graphData);
        updateStats();
        switchTab('info');
    }
    
    el.loginKey.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') login();
    });
    el.loginBtn.addEventListener('click', login);
    el.logoutBtn.addEventListener('click', logout);
    el.themeToggle.addEventListener('click', toggleTheme);
    el.sidebarToggle.addEventListener('click', toggleSidebar);

    el.sessionSelector.addEventListener('change', (e) => {
        const newSessionId = e.target.value;
        loadGraphData(newSessionId);
    });
    
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });
    
    el.searchInput.addEventListener('input', (e) => performSearch(e.target.value));
    el.debugQuery.addEventListener('keyup', (e) => {
        if (e.key === 'Enter') performDebugSearch();
    });
    el.debugSearchBtn.addEventListener('click', performDebugSearch);
    el.visualizeBtn.addEventListener('click', visualizeDebugResult);
    
    el.showLabels.addEventListener('change', (e) => {
        state.showLabels = e.target.checked;
        if (state.Graph) state.Graph.nodeCanvasObject(state.Graph.nodeCanvasObject());
    });
    
    el.reloadBtn.addEventListener('click', () => {
        state.selectedNode = null;
        state.highlightNodes.clear();
        state.highlightLinks.clear();
        if (state.currentSessionId) {
            loadGraphData(state.currentSessionId);
        } else {
            console.warn("No current session to reload.");
        }
    });
    
    el.fitViewBtn.addEventListener('click', () => {
        if (state.Graph) state.Graph.zoomToFit(400);
    });

    el.toolsBtn.addEventListener('click', showBatchOperationsModal);
    el.modalCloseBtn.addEventListener('click', closeModal);
    el.modalOverlay.addEventListener('click', (e) => {
        if (e.target === el.modalOverlay) {
            closeModal();
        }
    });

    // --- WebSocket 和监控功能 ---

    function connectWebSocket() {
        if (state.ws && state.ws.readyState === WebSocket.OPEN) return;

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${window.location.host}/ws/status`;
        state.ws = new WebSocket(url);

        state.ws.onopen = () => {
            console.log('WebSocket connected');
            addLogEntry({
                level: 'INFO',
                message: '监控服务已连接。',
                timestamp: new Date().toISOString()
            });
        };

        state.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                switch (data.type) {
                    case 'log':
                        addLogEntry(data.payload);
                        break;
                    case 'task':
                        addTaskEntry(data.payload);
                        break;
                    case 'message':
                        addMessageEntry(data.payload);
                        break;
                }
            } catch (e) {
                console.error('Error parsing WebSocket message:', e);
            }
        };

        state.ws.onclose = () => {
            console.log('WebSocket disconnected. Retrying in 3 seconds...');
            addLogEntry({
                level: 'WARNING',
                message: '监控服务已断开，3秒后重试...',
                timestamp: new Date().toISOString()
            });
            setTimeout(connectWebSocket, 3000);
        };

        state.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            addLogEntry({
                level: 'ERROR',
                message: '监控服务连接错误。',
                timestamp: new Date().toISOString()
            });
            state.ws.close();
        };
    }

    function addEntry(container, content, isHTML = false) {
        if (state.logPaused) return;
        const wasScrolledToBottom = container.scrollHeight - container.clientHeight <= container.scrollTop + 1;
        
        const entry = document.createElement('div');
        if (isHTML) {
            entry.innerHTML = content;
        } else {
            entry.textContent = content;
        }
        container.appendChild(entry);

        if (wasScrolledToBottom) {
            container.scrollTop = container.scrollHeight;
        }
    }

    function addLogEntry(log) {
        // 无论当前过滤器是什么，都将日志存入缓存
        state.logCache.push(log);
        // 如果日志级别匹配当前过滤器，则将其添加到视图
        if (shouldDisplayLog(log)) {
            renderLogEntry(log);
        }
    }

    function shouldDisplayLog(log) {
        return state.logLevel === 'ALL' || state.logLevel === log.level;
    }

    function renderLogEntry(log) {
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        entry.dataset.level = log.level;
        entry.innerHTML = `<span style="color: #999;">${new Date(log.timestamp).toLocaleTimeString()}</span> [${log.level}] ${log.message}`;
        
        el.monitorLogs.appendChild(entry);
        if (!state.logPaused) {
            el.monitorLogs.scrollTop = el.monitorLogs.scrollHeight;
        }
    }

    function rerenderLogs() {
        el.monitorLogs.innerHTML = '';
        state.logCache.forEach(log => {
            if (shouldDisplayLog(log)) {
                renderLogEntry(log);
            }
        });
    }

    function addTaskEntry(task) {
        addEntry(el.monitorTasks, `<span style="color: #999;">${new Date(task.timestamp).toLocaleTimeString()}</span> ${task.content}`, true);
    }

    function addMessageEntry(message) {
        addEntry(el.monitorMessages, `<span style="color: #999;">${new Date(message.timestamp).toLocaleTimeString()}</span> <strong>${message.sender}:</strong> ${message.text}`, true);
    }

    el.logLevelFilter.addEventListener('change', (e) => {
        state.logLevel = e.target.value;
        // 清空并重新筛选显示
        el.monitorLogs.innerHTML = '';
        // 这里可以重新请求历史日志或简单地等待新日志
    });

    el.logPauseToggle.addEventListener('click', () => {
        state.logPaused = !state.logPaused;
        el.logPauseToggle.textContent = state.logPaused ? '继续' : '暂停';
    });

    el.logClear.addEventListener('click', () => {
        el.monitorLogs.innerHTML = '';
    });
    
    lucide.createIcons();
    
    // 初始化主题
    if (state.isDark) {
        document.body.classList.add('dark');
        el.themeToggle.innerHTML = '<i data-lucide="moon" style="width: 1rem; height: 1rem;"></i>';
        lucide.createIcons();
    }

    checkSession();
})();