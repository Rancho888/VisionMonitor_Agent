<template>
  <div class="app-container" :data-theme="isDark ? 'dark' : 'light'">
    <!-- 顶部导航 -->
    <header class="header">
      <div class="header-left">
        <div class="logo">
          <span class="logo-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
          </span>
          <h1>视觉监控助手</h1>
        </div>
      </div>
      <div class="header-right">
        <div class="connection-status" :class="{ connected: wsConnected }">
          <span class="dot"></span>
          {{ wsConnected ? '已连接' : '未连接' }}
        </div>
        <button class="btn-icon" @click="toggleDarkMode" title="切换主题">
          <!-- 太阳图标 -->
          <svg v-if="isDark" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
          <!-- 月亮图标 -->
          <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        </button>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 左侧：监控面板（含标签切换） -->
      <section class="monitor-panel">
        <div class="panel-header">
          <div class="tabs">
            <button
              class="tab-btn"
              :class="{ active: activeTab === 'monitor' }"
              @click="activeTab = 'monitor'"
            ><svg class="tab-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg> 监控画面</button>
            <button
              class="tab-btn"
              :class="{ active: activeTab === 'persons' }"
              @click="activeTab = 'persons'; loadPersons()"
            ><svg class="tab-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> 人像库</button>
            <button
              class="tab-btn"
              :class="{ active: activeTab === 'cameras' }"
              @click="activeTab = 'cameras'; loadCameraDatabase()"
            ><svg class="tab-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg> 摄像头库</button>
            <button
              class="tab-btn"
              :class="{ active: activeTab === 'records' }"
              @click="activeTab = 'records'; loadRecordsSummary(); loadRecords()"
            ><svg class="tab-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg> 识别记录</button>
          </div>
          <div class="panel-actions">
            <template v-if="activeTab === 'monitor'">
              <button class="btn btn-sm" @click="refreshSnapshot"><svg class="btn-icon-inline" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg> 刷新</button>
              <select v-model="cameraSortBy" class="sort-select">
                <option value="default">默认排序</option>
                <option value="name">按名称</option>
                <option value="location">按位置</option>
                <option value="status">在线优先</option>
              </select>
              <button class="btn btn-sm btn-primary" @click="showAddCamera = true">＋ 添加摄像头</button>
            </template>
            <template v-else-if="activeTab === 'persons'">
              <button class="btn btn-sm" @click="loadPersons"><svg class="btn-icon-inline" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg> 刷新</button>
              <button class="btn btn-sm btn-primary" @click="showRegisterPerson = true">＋ 注册人员</button>
            </template>
            <template v-else-if="activeTab === 'cameras'">
              <button class="btn btn-sm" @click="loadCameraDatabase"><svg class="btn-icon-inline" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg> 刷新</button>
            </template>
          </div>
        </div>

        <!-- ===== 标签1：监控画面 ===== -->
        <template v-if="activeTab === 'monitor'">
          <div v-if="loading.cameras" class="loading-wrap" style="padding:16px">
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px">
              <div v-for="n in 2" :key="n" class="skeleton-row" style="height:200px;border-radius:12px"></div>
            </div>
          </div>
          <div v-else-if="cameras.length > 0" class="camera-grid">
            <div
              v-for="cam in sortedCameras"
              :key="cam.id"
              class="camera-card"
              :class="{ active: cam.running }"
            >
              <div class="camera-feed" @dblclick="openFullscreen(cam)" title="双击全屏查看">
                <img
                  v-if="cam.snapshotUrl"
                  :src="cam.snapshotUrl"
                  :style="cam.rotation ? { transform: 'rotate(' + cam.rotation + 'deg)' } : {}"
                  alt="监控画面"
                />
                <img
                  v-else-if="cam.snapshot"
                  :src="'data:image/jpeg;base64,' + cam.snapshot"
                  :style="cam.rotation ? { transform: 'rotate(' + cam.rotation + 'deg)' } : {}"
                  alt="监控画面"
                />
                <div v-else class="no-signal">
                  <svg class="no-signal-svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="1" y1="1" x2="23" y2="23"/><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"/><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"/><path d="M10.71 5.05A16 16 0 0 1 22.56 9"/><path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>
                  <span>无信号</span>
                </div>

                <!-- 右上角：人数标签 -->
                <div class="camera-overlay" v-if="cam.persons">
                  <span class="person-count" @click.stop="showPersonDetail(cam)" title="点击查看详情">
                    <svg class="person-count-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg> {{ cam.total_persons || 0 }}人
                    <template v-if="cam.unknown_persons > 0">
                      （{{ cam.unknown_persons }}未知）
                    </template>
                  </span>
                </div>

                <!-- 底部浮层：左侧信息 + 旋转按钮 + 启动/停止 -->
                <div class="camera-footer">
                  <div class="camera-meta">
                    <div class="camera-name">
                      <span class="status-dot" :class="cam.running ? 'online' : 'offline'"></span>
                      {{ cam.name }}
                    </div>
                    <div class="camera-location">
                      <svg class="inline-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                      {{ cam.location || '--' }}
                    </div>
                    <div class="camera-fps" v-if="cam.fps">{{ cam.fps }} FPS</div>
                  </div>
                  <div class="camera-actions">
                    <div v-if="cam.running" class="rotation-group">
                      <button class="btn btn-xs btn-rot" @click.stop="updateRotation(cam.id, 0)" :class="{ active: cam.rotation === 0 || !cam.rotation }">0°</button>
                      <button class="btn btn-xs btn-rot" @click.stop="updateRotation(cam.id, 90)" :class="{ active: cam.rotation === 90 }">90°</button>
                      <button class="btn btn-xs btn-rot" @click.stop="updateRotation(cam.id, 180)" :class="{ active: cam.rotation === 180 }">180°</button>
                      <button class="btn btn-xs btn-rot" @click.stop="updateRotation(cam.id, 270)" :class="{ active: cam.rotation === 270 }">270°</button>
                    </div>
                  <button
                    v-if="!cam.running"
                    class="btn btn-xs btn-success"
                    @click="startCamera(cam.id)"
                  >▶</button>
                  <button
                    v-else
                    class="btn btn-xs btn-danger"
                    @click="stopCamera(cam.id)"
                  >⏹</button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">
            <span class="empty-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
            </span>
            <p>暂无摄像头</p>
            <p class="text-sm text-slate-500">点击"添加摄像头"开始监控</p>
          </div>
        </template>

        <!-- ===== 标签2：人像库 ===== -->
        <template v-if="activeTab === 'persons'">
          <div class="data-panel">
            <div class="search-bar">
              <input
                type="text"
                v-model="personSearch"
                placeholder="搜索姓名 / 部门 / 类别..."
                @input="filterPersonList"
                class="search-input"
              />
            </div>
            <div class="table-wrap">
              <div v-if="loading.persons" class="loading-wrap">
                <div class="skeleton-row" v-for="n in 5" :key="n" :style="{ width: (100 - n * 10) + '%' }"></div>
              </div>
              <table v-else class="data-table">
                <thead>
                  <tr>
                    <th style="width:50px">头像</th>
                    <th class="sortable" @click="togglePersonSort('name')">姓名 {{ personSortIcon('name') }}</th>
                    <th>类别</th>
                    <th>部门</th>
                    <th class="sortable" @click="togglePersonSort('photo_count')">照片数 {{ personSortIcon('photo_count') }}</th>
                    <th class="sortable" @click="togglePersonSort('created_at')">入库时间 {{ personSortIcon('created_at') }}</th>
                    <th style="width:100px">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="p in sortedPersons" :key="p.id">
                    <td>
                      <div
                        class="avatar-cell"
                        @mouseenter="fetchAvatar(p.name, $event)"
                        @mouseleave="hideAvatarPreview"
                      >
                        <div class="avatar-thumb">
                          <img v-if="avatarCache[p.name]" :src="'data:image/jpeg;base64,' + avatarCache[p.name]" />
                          <span v-else class="thumb-placeholder">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                          </span>
                        </div>
                      </div>
                    </td>
                    <td><strong>{{ p.name }}</strong></td>
                    <td>
                      <span class="badge-tag" :class="p.category">
                        {{ categoryLabel(p.category) }}
                      </span>
                    </td>
                    <td>{{ p.department || '--' }}</td>
                    <td>
                      <span :class="(p.photo_count || 0) >= 3 ? 'text-green' : 'text-yellow'">
                        {{ p.photo_count || 0 }}张
                      </span>
                    </td>
                    <td>{{ formatDate(p.created_at) }}</td>
                    <td>
                      <div class="action-cell">
                        <button class="btn btn-xs" @click="openAddPhoto(p.name)" title="追加照片">
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
                        </button>
                        <button class="btn btn-xs btn-danger" @click="deletePersonConfirm(p.name)" title="删除">
                          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="filteredPersons.length === 0">
                    <td colspan="7"><div class="empty-state-small">暂无数据</div></td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="table-summary">
              共 {{ filteredPersons.length }} / {{ personList.length }} 人
            </div>
          </div>
        </template>

        <!-- ===== 标签3：摄像头库 ===== -->
        <template v-if="activeTab === 'cameras'">
          <div class="data-panel">
            <div class="search-bar">
              <input
                type="text"
                v-model="cameraDBSearch"
                placeholder="搜索设备名称 / 位置 / 编号..."
                @input="filterCameraDBList"
                class="search-input"
              />
              <select v-model="cameraDBStatusFilter" @change="filterCameraDBList" class="search-select">
                <option value="">全部状态</option>
                <option value="在线">在线</option>
                <option value="离线">离线</option>
              </select>
            </div>
            <div class="table-wrap">
              <div v-if="loading.cameraDB" class="loading-wrap">
                <div class="skeleton-row" v-for="n in 5" :key="n" :style="{ width: (100 - n * 10) + '%' }"></div>
              </div>
              <table v-else class="data-table">
                <thead>
                  <tr>
                    <th class="sortable" @click="toggleCameraDBSort('id')">设备编号 {{ cameraDBSortIcon('id') }}</th>
                    <th class="sortable" @click="toggleCameraDBSort('name')">设备名称 {{ cameraDBSortIcon('name') }}</th>
                    <th class="sortable" @click="toggleCameraDBSort('location')">位置 {{ cameraDBSortIcon('location') }}</th>
                    <th>分辨率</th>
                    <th class="sortable" @click="toggleCameraDBSort('fps')">FPS {{ cameraDBSortIcon('fps') }}</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="c in sortedCameraDB" :key="c.id">
                    <td><code class="code-tag">{{ c.id }}</code></td>
                    <td><strong>{{ c.name }}</strong></td>
                    <td>
                      <svg class="inline-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                      {{ c.location || '--' }}
                    </td>
                    <td>{{ c.resolution || '1920×1080' }}</td>
                    <td>{{ c.fps }}</td>
                    <td>
                      <span class="badge-tag" :class="c.status === '在线' ? 'online' : 'offline'">
                        {{ c.status }}
                      </span>
                    </td>
                    <td>
                      <div class="action-cell">
                        <button
                          v-if="c.status !== '在线'"
                          class="btn btn-xs btn-success"
                          @click="startCamera(c.id)"
                        >▶ 启动</button>
                        <button
                          v-else
                          class="btn btn-xs btn-danger"
                          @click="stopCamera(c.id)"
                        >⏹ 停止</button>
                        <button
                          class="btn btn-xs"
                          @click="openEditCamera(c)"
                        ><svg class="btn-icon-inline" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> 编辑</button>
                        <button
                          class="btn btn-xs btn-danger"
                          @click="deleteCameraConfirm(c.id, c.name)"
                        ><svg class="btn-icon-inline" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg> 删除</button>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="sortedCameraDB.length === 0">
                    <td colspan="7"><div class="empty-state-small">暂无数据</div></td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="table-summary">
              共 {{ sortedCameraDB.length }} / {{ cameraDBList.length }} 台
              &nbsp;|&nbsp;
              <span class="status-indicator online-dot"></span> 在线: {{ cameraDBList.filter(c => c.status === '在线').length }}
              &nbsp;
              <span class="status-indicator offline-dot"></span> 离线: {{ cameraDBList.filter(c => c.status !== '在线').length }}
            </div>
          </div>
        </template>

        <!-- ===== 标签4：识别记录 ===== -->
        <template v-if="activeTab === 'records'">
          <!-- 统计卡片 -->
          <div class="stats-row" v-if="recordsSummary.today_total !== null">
            <div class="stat-card">
              <div class="stat-value">{{ recordsSummary.today_total }}</div>
              <div class="stat-label">今日识别</div>
            </div>
            <div class="stat-card green">
              <div class="stat-value">{{ recordsSummary.today_known }}</div>
              <div class="stat-label">已知人员</div>
            </div>
            <div class="stat-card orange">
              <div class="stat-value">{{ recordsSummary.today_unknown }}</div>
              <div class="stat-label">陌生人</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{{ recordsSummary.active_cameras }}</div>
              <div class="stat-label">活跃摄像头</div>
            </div>
          </div>
          <!-- 搜索栏 -->
          <div class="search-bar">
            <input
              type="text"
              v-model="recordsFilter.person_name"
              placeholder="搜索姓名..."
              @input="debounceSearch"
              class="search-input"
            />
            <input
              type="datetime-local"
              v-model="recordsFilter.start_time"
              @change="loadRecords(1)"
              class="search-input"
              style="max-width:190px"
            />
            <input
              type="datetime-local"
              v-model="recordsFilter.end_time"
              @change="loadRecords(1)"
              class="search-input"
              style="max-width:190px"
            />
            <select v-model="recordsFilter.record_type" @change="loadRecords(1)" class="search-select">
              <option value="">全部类型</option>
              <option value="known">已知人员</option>
              <option value="unknown">陌生人</option>
            </select>
            <button class="btn btn-sm" @click="resetRecordsFilter"><svg class="btn-icon-inline" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg> 重置筛选</button>
            <button class="btn btn-sm btn-danger" @click="clearAllRecords"><svg class="btn-icon-inline" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg> 清空记录</button>
            <button class="btn btn-sm" @click="exportRecordsCSV"><svg class="btn-icon-inline" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg> 导出CSV</button>
            <button
              class="btn btn-sm"
              :class="{ 'btn-primary': recordsViewMode === 'grouped' }"
              @click="recordsViewMode = 'grouped'"
            ><svg class="btn-icon-inline" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg> 聚合</button>
            <button
              class="btn btn-sm"
              :class="{ 'btn-primary': recordsViewMode === 'detail' }"
              @click="recordsViewMode = 'detail'"
            ><svg class="btn-icon-inline" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg> 详细</button>
          </div>

          <!-- 聚合视图 -->
          <template v-if="recordsViewMode === 'grouped'">
            <div class="table-wrap">
              <div v-if="loading.records" class="loading-wrap">
                <div class="skeleton-row" v-for="n in 6" :key="n" :style="{ width: (100 - n * 10) + '%' }"></div>
              </div>
              <table v-else class="data-table">
                <thead>
                  <tr>
                    <th style="width:30px"></th>
                    <th>人员</th>
                    <th style="width:75px">次数</th>
                    <th style="width:75px">最高</th>
                    <th style="width:155px">最近出现</th>
                    <th>摄像头</th>
                  </tr>
                </thead>
                <tbody>
                  <template v-for="g in groupedRecords" :key="g.person_name">
                    <tr class="group-row" @click="togglePersonExpand(g.person_name)" style="cursor:pointer">
                      <td>
                        <span class="expand-icon">{{ expandedPersonNames.has(g.person_name) ? '▼' : '▶' }}</span>
                      </td>
                      <td>
                        <strong>{{ g.person_name }}</strong>
                      </td>
                      <td>
                        <span class="group-count">{{ g.count }}次</span>
                      </td>
                      <td>
                        <span :class="g.max_confidence >= 80 ? 'text-green' : g.max_confidence >= 50 ? 'text-yellow' : 'text-red'">
                          {{ g.max_confidence }}%
                        </span>
                      </td>
                      <td><code class="code-tag">{{ formatDate(g.latest_time) }}</code></td>
                      <td>
                        <template v-for="(cid, i) in [...g.camera_ids]" :key="cid">
                          <span class="badge-tag" style="margin-right:4px">{{ cid }}</span>
                        </template>
                      </td>
                    </tr>
                    <!-- 展开的详细行 -->
                    <tr v-if="expandedPersonNames.has(g.person_name)" class="detail-rows">
                      <td colspan="6" style="padding:0">
                        <div class="expanded-panel">
                          <table class="data-table sub-table">
                            <thead>
                              <tr>
                                <th style="width:155px">时间</th>
                                <th>摄像头</th>
                                <th style="width:75px">置信度</th>
                                <th style="width:75px">类型</th>
                                <th style="width:60px">截图</th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr v-for="r in g.records" :key="r.id">
                                <td><code class="code-tag">{{ formatDate(r.detected_at) }}</code></td>
                                <td><span class="text-muted">{{ r.camera_id }}</span></td>
                                <td>
                                  <span :class="r.confidence >= 80 ? 'text-green' : r.confidence >= 50 ? 'text-yellow' : 'text-red'">
                                    {{ r.confidence }}%
                                  </span>
                                </td>
                                <td>
                                  <span class="badge-tag" :class="r.is_unknown ? 'unknown' : 'known'">
                                    {{ r.is_unknown ? '陌生人' : '已知' }}
                                  </span>
                                </td>
                                <td>
                                  <div
                                    v-if="r.snapshot_path"
                                    class="avatar-cell"
                                    @mouseenter="fetchSnapshot(r.id, $event)"
                                    @mouseleave="hideAvatarPreview"
                                  >
                                    <div class="avatar-thumb">
                                      <img v-if="snapshotCache[r.id]" :src="'data:image/jpeg;base64,' + snapshotCache[r.id]" />
                                      <span v-else class="thumb-placeholder">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
                                      </span>
                                    </div>
                                  </div>
                                  <span v-else class="text-muted">--</span>
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </td>
                    </tr>
                  </template>
                  <tr v-if="groupedRecords.length === 0">
                    <td colspan="6"><div class="empty-state-small">暂无识别记录</div></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>

          <!-- 详细视图（原表格） -->
          <div v-else class="table-wrap">
            <div v-if="loading.records" class="loading-wrap">
              <div class="skeleton-row" v-for="n in 6" :key="n" :style="{ width: (100 - n * 10) + '%' }"></div>
            </div>
            <table v-else class="data-table">
              <thead>
                <tr>
                  <th class="sortable" style="width:155px" @click="toggleRecordsDetailSort('detected_at')">时间 {{ recordsDetailSortIcon('detected_at') }}</th>
                  <th class="sortable" @click="toggleRecordsDetailSort('camera_id')">摄像头 {{ recordsDetailSortIcon('camera_id') }}</th>
                  <th>姓名</th>
                  <th class="sortable" style="width:75px" @click="toggleRecordsDetailSort('confidence')">置信度 {{ recordsDetailSortIcon('confidence') }}</th>
                  <th style="width:75px">类型</th>
                  <th style="width:60px">截图</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in sortedRecordsList" :key="r.id">
                  <td><code class="code-tag">{{ formatDate(r.detected_at) }}</code></td>
                  <td><span class="text-muted">{{ r.camera_id }}</span></td>
                  <td><strong>{{ getPersonDisplayName(r) }}</strong></td>
                  <td>
                    <span :class="r.confidence >= 80 ? 'text-green' : r.confidence >= 50 ? 'text-yellow' : 'text-red'">
                      {{ r.confidence }}%
                    </span>
                  </td>
                  <td>
                    <span class="badge-tag" :class="r.is_unknown ? 'unknown' : 'known'">
                      {{ r.is_unknown ? '陌生人' : '已知' }}
                    </span>
                  </td>
                  <td>
                    <div
                      v-if="r.snapshot_path"
                      class="avatar-cell"
                      @mouseenter="fetchSnapshot(r.id, $event)"
                      @mouseleave="hideAvatarPreview"
                    >
                      <div class="avatar-thumb">
                        <img v-if="snapshotCache[r.id]" :src="'data:image/jpeg;base64,' + snapshotCache[r.id]" />
                        <span v-else class="thumb-placeholder">
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
                        </span>
                      </div>
                    </div>
                    <span v-else class="text-muted">--</span>
                  </td>
                </tr>
                <tr v-if="sortedRecordsList.length === 0">
                  <td colspan="6"><div class="empty-state-small">暂无识别记录</div></td>
                </tr>
              </tbody>
            </table>
          </div>
          <!-- 分页 -->
          <div class="pagination" v-if="recordsTotalPages > 1">
            <button class="btn btn-sm" :disabled="recordsPage <= 1" @click="loadRecords(recordsPage - 1)">◀ 上一页</button>
            <span class="page-info">第 {{ recordsPage }} / {{ recordsTotalPages }} 页（共 {{ recordsTotal }} 条）</span>
            <button class="btn btn-sm" :disabled="recordsPage >= recordsTotalPages" @click="loadRecords(recordsPage + 1)">下一页 ▶</button>
          </div>
          <div class="table-summary" v-else>
            共 {{ recordsTotal }} 条记录
          </div>
        </template>
      </section>

      <!-- 右侧：对话面板 -->
      <section class="chat-panel">
        <div class="panel-header">
          <h2><svg class="inline-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg> 智能对话</h2>
          <div class="panel-header-right">
            <span class="text-xs text-slate-500">AI助手在线</span>
            <button
              v-if="messages.length > 0"
              class="clear-chat-btn"
              @click="clearAllMessages"
              title="清空所有对话"
            ><svg class="btn-icon-inline" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg> 清空</button>
          </div>
        </div>

        <!-- 消息列表 -->
        <div class="chat-messages" ref="chatMessages">
          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            class="message"
            :class="msg.role"
          >
            <div class="message-avatar">
              <!-- 用户头像 -->
              <svg v-if="msg.role === 'user'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              <!-- AI助手头像 -->
              <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></svg>
            </div>
            <div class="message-content">
              <button
                class="msg-delete-btn"
                @click="deleteMessage(idx)"
                title="删除此条消息"
              >×</button>
              <div class="message-bubble" v-html="formatMessage(msg.content)"></div>
              <div class="message-time">{{ msg.time }}</div>
            </div>
          </div>

          <!-- 正在输入 -->
          <div v-if="isTyping" class="message assistant">
            <div class="message-avatar">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></svg>
            </div>
            <div class="message-content">
              <div class="message-bubble typing">
                <span class="typing-dots">
                  <span></span><span></span><span></span>
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 快捷指令 -->
        <div class="quick-commands" v-if="messages.length <= 2">
          <button
            v-for="cmd in quickCommands"
            :key="cmd"
            class="quick-cmd"
            @click="sendMessage(cmd)"
          >
            {{ cmd }}
          </button>
        </div>

        <!-- 输入框 -->
        <div class="chat-input-area">
          <textarea
            v-model="inputMessage"
            @keydown.enter.exact.prevent="sendMessage(inputMessage)"
            @keydown.enter.shift.exact="inputMessage += '\n'"
            placeholder="输入消息... (Enter发送, Shift+Enter换行)"
            rows="1"
            ref="inputArea"
            :disabled="isTyping"
          ></textarea>
          <button
            class="btn btn-primary send-btn"
            @click="sendMessage(inputMessage)"
            :disabled="!inputMessage.trim() || isTyping"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
          </button>
        </div>
      </section>
    </main>

    <!-- 添加摄像头弹窗 -->
    <div v-if="showAddCamera" class="modal-overlay" @click.self="showAddCamera = false">
      <div class="modal">
        <h3>添加摄像头</h3>
        <div class="form-group">
          <label>名称</label>
          <input v-model="newCamera.name" placeholder="例如：大厅摄像头" />
        </div>
        <div class="form-group">
          <label>视频源</label>
          <input v-model="newCamera.source" placeholder="0=本地摄像头, 或 RTSP地址" />
        </div>
        <div class="form-group">
          <label>位置</label>
          <input v-model="newCamera.location" placeholder="例如：1楼大厅" />
        </div>
        <div class="form-group">
          <label>FPS</label>
          <input v-model.number="newCamera.fps" type="number" min="1" max="30" />
        </div>
        <div class="form-group">
          <label>画面旋转</label>
          <select v-model.number="newCamera.rotation">
            <option :value="0">0°（正常）</option>
            <option :value="90">90°（手机竖拍 → 横屏）</option>
            <option :value="180">180°</option>
            <option :value="270">270°（手机倒置）</option>
          </select>
        </div>
        <div class="modal-actions">
          <button class="btn" @click="showAddCamera = false">取消</button>
          <button class="btn btn-primary" @click="addCamera">确认添加</button>
        </div>
      </div>
    </div>

    <!-- 编辑摄像头弹窗 -->
    <div v-if="showEditCamera" class="modal-overlay" @click.self="showEditCamera = false">
      <div class="modal">
        <h3>编辑摄像头</h3>
        <div class="form-group">
          <label>设备编号</label>
          <input :value="editingCamera.id" disabled style="opacity:0.5" />
        </div>
        <div class="form-group">
          <label>名称</label>
          <input v-model="editingCamera.name" placeholder="例如：大厅摄像头" />
        </div>
        <div class="form-group">
          <label>视频源</label>
          <input v-model="editingCamera.source" placeholder="0=本地摄像头, 或 RTSP地址" />
        </div>
        <div class="form-group">
          <label>位置</label>
          <input v-model="editingCamera.location" placeholder="例如：1楼大厅" />
        </div>
        <div class="form-group">
          <label>FPS</label>
          <input v-model.number="editingCamera.fps" type="number" min="1" max="30" />
        </div>
        <div class="form-group">
          <label>画面旋转</label>
          <select v-model.number="editingCamera.rotation">
            <option :value="0">0°（正常）</option>
            <option :value="90">90°（手机竖拍 → 横屏）</option>
            <option :value="180">180°</option>
            <option :value="270">270°（手机倒置）</option>
          </select>
        </div>
        <div class="modal-actions">
          <button class="btn" @click="showEditCamera = false">取消</button>
          <button class="btn btn-primary" @click="updateCamera">保存修改</button>
        </div>
      </div>
    </div>

    <!-- 注册人员弹窗 -->
    <div v-if="showRegisterPerson" class="modal-overlay" @click.self="showRegisterPerson = false">
      <div class="modal">
        <h3>注册人员</h3>
        <div class="form-group">
          <label>姓名 *</label>
          <input v-model="registerForm.name" placeholder="例如：张三" />
        </div>
        <div class="form-group">
          <label>类别</label>
          <select v-model="registerForm.category" class="form-select">
            <option value="staff">员工</option>
            <option value="visitor">访客</option>
            <option value="blacklist">黑名单</option>
          </select>
        </div>
        <div class="form-group">
          <label>部门</label>
          <input v-model="registerForm.department" placeholder="例如：技术部" />
        </div>
        <div class="form-group">
          <label>照片 *（可多选，支持 Ctrl+点击）</label>
          <div class="file-upload-zone" @click="$refs.registerFileInput.click()" @dragover.prevent @drop.prevent="onRegisterDrop">
            <span v-if="registerForm.files.length === 0">
              <svg class="inline-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
              点击或拖拽上传照片
            </span>
            <span v-else>已选 {{ registerForm.files.length }} 张照片</span>
          </div>
          <input ref="registerFileInput" type="file" accept="image/*" multiple hidden @change="onRegisterFileChange" />
        </div>
        <div class="modal-actions">
          <button class="btn" @click="showRegisterPerson = false; resetRegisterForm()">取消</button>
          <button class="btn btn-primary" @click="registerPerson" :disabled="!registerForm.name || registerForm.files.length === 0">确认注册</button>
        </div>
      </div>
    </div>

    <!-- 追加照片弹窗 -->
    <div v-if="showAddPhoto" class="modal-overlay" @click.self="showAddPhoto = false">
      <div class="modal">
        <h3>为「{{ addPhotoTarget }}」追加照片</h3>
        <div class="form-group">
          <div class="file-upload-zone" @click="$refs.addPhotoFileInput.click()" @dragover.prevent @drop.prevent="onAddPhotoDrop">
            <span v-if="addPhotoFiles.length === 0">
              <svg class="inline-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
              点击或拖拽上传照片
            </span>
            <span v-else>已选 {{ addPhotoFiles.length }} 张照片</span>
          </div>
          <input ref="addPhotoFileInput" type="file" accept="image/*" multiple hidden @change="onAddPhotoFileChange" />
        </div>
        <div class="modal-actions">
          <button class="btn" @click="showAddPhoto = false; addPhotoFiles = []">取消</button>
          <button class="btn btn-primary" @click="addPhoto" :disabled="addPhotoFiles.length === 0">确认追加</button>
        </div>
      </div>
    </div>

    <!-- 头像悬浮预览 -->
    <div
      v-if="avatarPreview.visible"
      class="avatar-preview"
      :style="{ top: avatarPreview.y + 'px', left: avatarPreview.x + 'px' }"
    >
      <img v-if="avatarPreview.src" :src="avatarPreview.src" alt="头像" />
      <span v-else>加载中...</span>
    </div>

    <!-- Toast 通知 -->
    <div class="toast-container" v-if="toast.visible">
      <div class="toast-item" :class="toast.type">
        <span class="toast-icon">
          <svg v-if="toast.type === 'success'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
          <svg v-else-if="toast.type === 'error'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
          <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
        </span>
        <span>{{ toast.message }}</span>
      </div>
    </div>

    <!-- 确认弹窗 -->
    <div v-if="confirmDialog.visible" class="confirm-overlay" @click.self="confirmDialog.onCancel?.()">
      <div class="confirm-modal">
        <div class="confirm-icon">
          <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
        </div>
        <h3>{{ confirmDialog.title }}</h3>
        <p>{{ confirmDialog.message }}</p>
        <div class="confirm-actions">
          <button class="btn" @click="confirmDialog.onCancel?.()">取消</button>
          <button class="btn btn-danger" @click="confirmDialog.onConfirm?.()">确认</button>
        </div>
      </div>
    </div>

    <!-- 全屏查看弹窗 -->
    <div v-if="fullscreen.visible" class="fullscreen-overlay" @click.self="closeFullscreen" @keydown.esc="closeFullscreen">
      <div class="fullscreen-header">
        <span class="fullscreen-title">
          <svg class="inline-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></svg>
          {{ fullscreen.cameraName }}
        </span>
        <button class="btn btn-sm" @click="closeFullscreen">✕ 关闭</button>
      </div>
      <div class="fullscreen-body">
        <img
          v-if="fullscreen.src"
          :src="fullscreen.src"
          :style="fullscreen.rotation ? { transform: 'rotate(' + fullscreen.rotation + 'deg)' } : {}"
          alt="全屏监控画面"
        />
        <div v-else class="no-signal">
          <svg class="no-signal-svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="1" y1="1" x2="23" y2="23"/><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"/><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"/><path d="M10.71 5.05A16 16 0 0 1 22.56 9"/><path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>
          <span>无信号</span>
        </div>
      </div>
    </div>

    <!-- 人数详情弹窗 -->
    <div v-if="personDetailDialog.visible" class="modal-overlay" @click.self="personDetailDialog.visible = false">
      <div class="modal" style="max-width:560px">
        <h3>
          <svg class="inline-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
          {{ personDetailDialog.cameraName }} — 当前画面人员
        </h3>
        <div class="search-bar" style="padding:8px 0 12px;border-bottom:none">
          <input
            type="text"
            v-model="personDetailDialog.search"
            placeholder="搜索姓名..."
            class="search-input"
          />
          <select v-model="personDetailDialog.filterType" class="search-select">
            <option value="">全部类型</option>
            <option value="known">已注册</option>
            <option value="unknown">陌生人</option>
          </select>
        </div>
        <div v-if="filteredPersonDetail.length === 0" class="empty-state" style="padding:20px">
          <p>{{ personDetailDialog.search || personDetailDialog.filterType ? '无匹配结果' : '暂无人员数据' }}</p>
        </div>
        <table v-else class="data-table" style="margin-top:0">
          <thead>
            <tr>
              <th style="width:50px">#</th>
              <th>姓名</th>
              <th>类型</th>
              <th>相似度</th>
              <th>检测分</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(p, i) in filteredPersonDetail" :key="i" :class="{ 'row-unknown': p.is_unknown }">
              <td>{{ i + 1 }}</td>
              <td>{{ p.is_unknown ? '陌生人' : p.name }}</td>
              <td>
                <span class="badge" :class="p.is_unknown ? 'badge-unknown' : 'badge-known'">
                  {{ p.is_unknown ? '未知' : '已注册' }}
                </span>
              </td>
              <td>{{ p.confidence != null ? (p.confidence * 100).toFixed(1) + '%' : '--' }}</td>
              <td>{{ p.detection_score != null ? (p.detection_score * 100).toFixed(1) + '%' : '--' }}</td>
            </tr>
          </tbody>
        </table>
        <div class="modal-actions" style="margin-top:16px">
          <button class="btn" @click="personDetailDialog.visible = false">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, onBeforeUnmount } from 'vue'
import axios from 'axios'

// ========== 状态 ==========
const wsConnected = ref(false)
const isDark = ref(false)
const messages = ref([])
const inputMessage = ref('')
const isTyping = ref(false)
const chatMessages = ref(null)
const inputArea = ref(null)

const cameras = ref([])
const cameraSortBy = ref('default')  // 'default' | 'name' | 'location' | 'status'
const sortedCameras = computed(() => {
  const list = [...cameras.value]
  switch (cameraSortBy.value) {
    case 'name': return list.sort((a, b) => (a.name || '').localeCompare(b.name || ''))
    case 'location': return list.sort((a, b) => (a.location || '').localeCompare(b.location || ''))
    case 'status': return list.sort((a, b) => (b.running ? 1 : 0) - (a.running ? 1 : 0))
    default: return list
  }
})
const showAddCamera = ref(false)
const newCamera = ref({ name: '', source: '0', location: '', fps: 15, rotation: 0 })
const fullscreen = ref({ visible: false, src: '', cameraName: '', rotation: 0 })
function openFullscreen(cam) {
  fullscreen.value = {
    visible: true,
    src: cam.snapshotUrl || (cam.snapshot ? 'data:image/jpeg;base64,' + cam.snapshot : ''),
    cameraName: cam.name,
    rotation: cam.rotation || 0,
  }
}
function closeFullscreen() {
  fullscreen.value = { visible: false, src: '', cameraName: '', rotation: 0 }
}

// 标签切换
const activeTab = ref('monitor')

// 人像库
const personList = ref([])
const filteredPersons = ref([])
const personSearch = ref('')
const personSortBy = ref({ field: '', order: 'asc' })  // field: 'name'|'photo_count'|'created_at'
const sortedPersons = computed(() => {
  const list = [...filteredPersons.value]
  const { field, order } = personSortBy.value
  if (!field) return list
  return list.sort((a, b) => {
    let va = a[field], vb = b[field]
    if (field === 'photo_count') { va = va || 0; vb = vb || 0 }
    if (field === 'created_at') { va = va || ''; vb = vb || '' }
    const cmp = typeof va === 'string' ? va.localeCompare(vb) : va - vb
    return order === 'asc' ? cmp : -cmp
  })
})
function togglePersonSort(field) {
  const cur = personSortBy.value
  if (cur.field === field) {
    personSortBy.value = { field, order: cur.order === 'asc' ? 'desc' : 'asc' }
  } else {
    personSortBy.value = { field, order: 'asc' }
  }
}
function personSortIcon(field) {
  const cur = personSortBy.value
  if (cur.field !== field) return '↕'
  return cur.order === 'asc' ? '↑' : '↓'
}

// 摄像头库
const cameraDBList = ref([])
const filteredCameraDB = ref([])
const cameraDBSearch = ref('')
const cameraDBStatusFilter = ref('')
const cameraDBSortBy = ref({ field: '', order: 'asc' })
const sortedCameraDB = computed(() => {
  const list = [...filteredCameraDB.value]
  const { field, order } = cameraDBSortBy.value
  if (!field) return list
  return list.sort((a, b) => {
    let va = a[field], vb = b[field]
    if (field === 'fps') { va = va || 0; vb = vb || 0 }
    if (typeof va === 'string') return order === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
    return order === 'asc' ? va - vb : vb - va
  })
})
function toggleCameraDBSort(field) {
  const cur = cameraDBSortBy.value
  if (cur.field === field) {
    cameraDBSortBy.value = { field, order: cur.order === 'asc' ? 'desc' : 'asc' }
  } else {
    cameraDBSortBy.value = { field, order: 'asc' }
  }
}
function cameraDBSortIcon(field) {
  const cur = cameraDBSortBy.value
  if (cur.field !== field) return '↕'
  return cur.order === 'asc' ? '↑' : '↓'
}
const showEditCamera = ref(false)
const editingCamera = ref({ id: '', name: '', source: '', location: '', fps: 15, rotation: 0 })

// 人像库 — 注册 / 追加 / 头像
const showRegisterPerson = ref(false)
const registerForm = ref({ name: '', category: 'staff', department: '', files: [] })
const showAddPhoto = ref(false)
const addPhotoTarget = ref('')
const addPhotoFiles = ref([])
const avatarCache = ref({})          // {name: base64}
const avatarPreview = ref({ visible: false, x: 0, y: 0, src: '' })
const snapshotCache = ref({})         // {record_id: base64}

// 人数详情弹窗
const personDetailDialog = ref({ visible: false, cameraName: '', persons: [], search: '', filterType: '' })
const filteredPersonDetail = computed(() => {
  const { persons, search, filterType } = personDetailDialog.value
  if (!persons) return []
  let list = persons
  if (search) {
    const kw = search.toLowerCase()
    list = list.filter(p => (p.name || '').toLowerCase().includes(kw) || (p.is_unknown && '陌生人'.includes(kw)))
  }
  if (filterType) {
    if (filterType === 'known') list = list.filter(p => !p.is_unknown)
    else if (filterType === 'unknown') list = list.filter(p => p.is_unknown)
  }
  return list
})
function showPersonDetail(cam) {
  personDetailDialog.value = {
    visible: true,
    cameraName: cam.name,
    persons: cam.persons || [],
    search: '',
    filterType: '',
  }
}

// Toast 通知
const toast = ref({ visible: false, message: '', type: 'info' })
let toastTimer = null
function showToast(message, type = 'info') {
  clearTimeout(toastTimer)
  toast.value = { visible: true, message, type }
  toastTimer = setTimeout(() => { toast.value = { visible: false, message: '', type: 'info' } }, 3000)
}

// 确认弹窗
const confirmDialog = ref({ visible: false, title: '', message: '', icon: 'warning', onConfirm: null, onCancel: null })
function showConfirm(title, message, onConfirm, icon = 'warning') {
  return new Promise((resolve) => {
    confirmDialog.value = {
      visible: true, title, message, icon,
      onConfirm: () => { confirmDialog.value.visible = false; onConfirm?.(); resolve(true) },
      onCancel: () => { confirmDialog.value.visible = false; resolve(false) },
    }
  })
}

// 识别记录
const recordsList = ref([])
const recordsPage = ref(1)
const recordsTotal = ref(0)
const recordsTotalPages = ref(1)
const recordsSummary = ref({ today_total: null, today_known: 0, today_unknown: 0, yesterday_total: 0, total_all: 0, active_cameras: 0 })
const recordsFilter = ref({ person_name: '', start_time: '', end_time: '', record_type: '' })
let recordsDebounceTimer = null

// 聚合视图
const recordsViewMode = ref('grouped') // 'grouped' | 'detail'
const expandedPersonNames = ref(new Set())
const recordsDetailSortBy = ref({ field: '', order: 'asc' })
const sortedRecordsList = computed(() => {
  const list = [...recordsList.value]
  const { field, order } = recordsDetailSortBy.value
  if (!field) return list
  return list.sort((a, b) => {
    let va = a[field], vb = b[field]
    if (field === 'confidence') { va = va || 0; vb = vb || 0 }
    if (typeof va === 'string') return order === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
    return order === 'asc' ? va - vb : vb - va
  })
})
function toggleRecordsDetailSort(field) {
  const cur = recordsDetailSortBy.value
  if (cur.field === field) {
    recordsDetailSortBy.value = { field, order: cur.order === 'asc' ? 'desc' : 'asc' }
  } else {
    recordsDetailSortBy.value = { field, order: 'asc' }
  }
}
function recordsDetailSortIcon(field) {
  const cur = recordsDetailSortBy.value
  if (cur.field !== field) return '↕'
  return cur.order === 'asc' ? '↑' : '↓'
}

// Loading 状态
const loading = ref({ cameras: false, persons: false, cameraDB: false, records: false })

// 按人员聚合当前页记录
const groupedRecords = computed(() => {
  const map = new Map()
  for (const r of recordsList.value) {
    const displayName = getPersonDisplayName(r)
    if (!map.has(displayName)) {
      map.set(displayName, {
        person_name: displayName,
        is_unknown: r.is_unknown,
        count: 0,
        max_confidence: 0,
        latest_time: r.detected_at,
        camera_ids: new Set(),
        records: [],
      })
    }
    const g = map.get(displayName)
    g.count++
    if (r.confidence > g.max_confidence) g.max_confidence = r.confidence
    if (r.detected_at > g.latest_time) g.latest_time = r.detected_at
    g.camera_ids.add(r.camera_id || '--')
    g.records.push(r)
  }
  return Array.from(map.values())
})

function togglePersonExpand(name) {
  const set = expandedPersonNames.value
  if (set.has(name)) {
    set.delete(name)
  } else {
    set.add(name)
  }
  // 触发响应式更新：重新赋值 Set
  expandedPersonNames.value = new Set(set)
}

let ws = null
const cameraWsMap = {}   // camera_id → WebSocket（每摄像头一个实时流）

const quickCommands = [
  '现在监控画面里有什么人？',
  '查看最近24小时记录',
  '本周人员统计排名',
  '有哪些摄像头在线？',
]

// ========== WebSocket ==========
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/api/chat/ws/default`

  ws = new WebSocket(wsUrl)

  ws.onopen = () => {
    wsConnected.value = true
  }

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)

    switch (data.type) {
      case 'connected':
        addMessage('assistant', data.message)
        break
      case 'status':
        // 处理中
        break
      case 'chat_chunk':
        // 流式更新最后一条消息
        updateLastAssistantMessage(data.content)
        break
      case 'chat_done':
        isTyping.value = false
        break
      case 'error':
        addMessage('assistant', `错误: ${data.message}`)
        isTyping.value = false
        break
    }
  }

  ws.onclose = () => {
    wsConnected.value = false
    // 5秒后重连
    setTimeout(connectWebSocket, 5000)
  }

  ws.onerror = () => {
    wsConnected.value = false
  }
}

// ========== 消息管理 ==========
function addMessage(role, content) {
  messages.value.push({
    role,
    content,
    time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
  })
  saveMessages()
  scrollToBottom()
}

function deleteMessage(index) {
  messages.value.splice(index, 1)
  saveMessages()
}

function clearAllMessages() {
  if (confirm('确定要清空所有对话记录吗？此操作不可恢复。')) {
    messages.value = []
    try { localStorage.removeItem('vision-monitor-chat') } catch {}
  }
}

function saveMessages() {
  try {
    // 只保留最近200条，避免 localStorage 溢出
    const recent = messages.value.slice(-200)
    localStorage.setItem('vision-monitor-chat', JSON.stringify(recent))
  } catch {}
}

function loadMessages() {
  try {
    const saved = localStorage.getItem('vision-monitor-chat')
    if (saved) {
      messages.value = JSON.parse(saved)
    }
  } catch {}
}

function updateLastAssistantMessage(chunk) {
  const lastMsg = messages.value[messages.value.length - 1]
  if (lastMsg && lastMsg.role === 'assistant') {
    lastMsg.content += chunk
  } else {
    addMessage('assistant', chunk)
  }
  scrollToBottom()
}

function sendMessage(text) {
  if (!text || !text.trim() || isTyping.value) return

  addMessage('user', text.trim())
  inputMessage.value = ''
  isTyping.value = true

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'chat', message: text.trim() }))
  } else {
    // fallback: HTTP 请求
    axios.post('/api/chat/send', { message: text.trim() })
      .then(res => {
        addMessage('assistant', res.data.message)
        isTyping.value = false
      })
      .catch(err => {
        addMessage('assistant', '请求失败: ' + err.message)
        isTyping.value = false
      })
  }
}

function formatMessage(content) {
  // 简单的 markdown 转 HTML
  return content
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
}

function scrollToBottom() {
  nextTick(() => {
    if (chatMessages.value) {
      chatMessages.value.scrollTop = chatMessages.value.scrollHeight
    }
  })
}

// ========== 摄像头 ==========
async function loadCameras(showLoading = true) {
  if (showLoading) loading.value.cameras = true
  try {
    const res = await axios.get('/api/camera/list')
    const online = res.data.online || {}
    const configured = res.data.configured || []

    // 构建旧数据索引
    const oldMap = {}
    cameras.value.forEach(c => { oldMap[c.id] = c })

    // 增量合并：逐个更新已有摄像头（避免整体替换数组导致画面闪烁）
    const newIds = new Set(configured.map(c => c.id))

    // 1. 删除后端已不存在的摄像头
    for (let i = cameras.value.length - 1; i >= 0; i--) {
      if (!newIds.has(cameras.value[i].id)) {
        cameras.value.splice(i, 1)
      }
    }

    // 2. 更新已有摄像头 + 新增摄像头
    configured.forEach(c => {
      const onlineInfo = online[c.id] || {}
      const cachedResult = onlineInfo.latest_result
      const existing = oldMap[c.id]

      if (existing) {
        // 已有摄像头：只更新可变属性，snapshotUrl/_blobUrl 由 WebSocket 独立管理不动
        existing.name = c.name
        existing.source = c.source
        existing.location = c.location
        existing.fps = c.fps
        existing.rotation = c.rotation || 0
        existing.running = onlineInfo.running || false
        // snapshot：仅当无 WebSocket 实时流且后端有新缓存时才更新
        if (cachedResult?.image_base64 && !existing.snapshotUrl) {
          existing.snapshot = cachedResult.image_base64
        }
        // persons/total/unknown：后端检测缓存优先
        if (cachedResult) {
          existing.persons = cachedResult.persons
          existing.total_persons = cachedResult.total_persons ?? existing.total_persons
          existing.unknown_persons = cachedResult.unknown_persons ?? existing.unknown_persons
        }
      } else {
        // 新增摄像头
        cameras.value.push({
          id: c.id,
          name: c.name,
          source: c.source,
          location: c.location,
          fps: c.fps,
          rotation: c.rotation || 0,
          running: onlineInfo.running || false,
          snapshot: cachedResult?.image_base64 || null,
          snapshotUrl: null,
          _blobUrl: null,
          persons: cachedResult?.persons || null,
          total_persons: cachedResult?.total_persons ?? 0,
          unknown_persons: cachedResult?.unknown_persons ?? 0,
        })
      }

      // 为已在运行但未建立 WebSocket 的摄像头自动连接
      if (onlineInfo.running && !cameraWsMap[c.id]) {
        connectCameraStream(c.id)
      }
    })
  } catch (e) {
    console.error('加载摄像头失败:', e)
  } finally {
    if (showLoading) loading.value.cameras = false
  }
}

async function refreshSnapshot() {
  for (const cam of cameras.value) {
    if (!cam.running) continue
    // 已有 WebSocket 实时流 → 跳过轮询（避免重复请求）
    if (cameraWsMap[cam.id] && cameraWsMap[cam.id].readyState === WebSocket.OPEN) continue
    try {
      const res = await axios.get(`/api/camera/snapshot/${cam.id}`)
      cam.snapshot = res.data.image_base64
      cam.total_persons = res.data.total_persons
      cam.unknown_persons = res.data.unknown_persons
      cam.persons = res.data.persons
    } catch (e) {
      console.error(`获取 ${cam.id} 画面失败:`, e)
    }
  }
}

async function addCamera() {
  try {
    await axios.post('/api/camera/add', {
      id: `cam_${Date.now()}`,
      name: newCamera.value.name,
      source: newCamera.value.source,
      location: newCamera.value.location,
      fps: newCamera.value.fps,
      rotation: newCamera.value.rotation,
    })
    showAddCamera.value = false
    newCamera.value = { name: '', source: '0', location: '', fps: 15, rotation: 0 }
    await loadCameras()
  } catch (e) {
    showToast('添加失败: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

async function startCamera(id) {
  try {
    await axios.post(`/api/camera/start/${id}`)
    await loadCameras()
    refreshSnapshot()
    // 为启动的摄像头建立 WebSocket 实时流
    connectCameraStream(id)
  } catch (e) {
    const detail = e.response?.data?.detail || e.message
    showToast('启动失败: ' + detail, 'error')
  }
}

async function stopCamera(id) {
  try {
    await axios.post(`/api/camera/stop/${id}`)
    disconnectCameraStream(id)
    // 立即清除画面，显示无信号
    const cam = cameras.value.find(c => c.id === id)
    if (cam) {
      cam.snapshot = null
      cam.snapshotUrl = null
      cam.persons = null
      cam.total_persons = 0
      cam.unknown_persons = 0
    }
    await loadCameras()
  } catch (e) {
    showToast('停止失败: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

async function updateRotation(cameraId, rotation) {
  try {
    await axios.post('/api/camera/update-rotation', null, { params: { camera_id: cameraId, rotation } })
    // 同步本地状态，立即生效（不用等 loadCameras）
    const cam = cameras.value.find(c => c.id === cameraId)
    if (cam) cam.rotation = rotation
  } catch (e) {
    showToast('旋转失败: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

// ========== 摄像头实时 WebSocket 流 ==========
function connectCameraStream(cameraId) {
  // 已有连接则跳过
  if (cameraWsMap[cameraId] && cameraWsMap[cameraId].readyState === WebSocket.OPEN) return

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const wsUrl = `${protocol}//${window.location.host}/api/camera/stream/${cameraId}`
  const camWs = new WebSocket(wsUrl)

  camWs.onopen = () => {
    console.log(`[视频流] 已连接: ${cameraId}`)
    const cam = cameras.value.find(c => c.id === cameraId)
    if (cam) showToast(`「${cam.name}」视频流已连接`, 'success')
  }

  camWs.onmessage = async (event) => {
    try {
      // 二进制帧（优化路径：JPEG 直接推送，无 base64 开销）
      // 兼容 Blob（默认 binaryType）和 ArrayBuffer（部分浏览器/代理）
      const isBinary = event.data instanceof Blob || event.data instanceof ArrayBuffer
      if (isBinary) {
        const buffer = event.data instanceof ArrayBuffer
          ? event.data
          : await event.data.arrayBuffer()
        const view = new DataView(buffer)
        const metaLen = view.getUint32(0, false)  // big-endian uint32
        const metaBytes = new Uint8Array(buffer, 4, metaLen)
        const meta = JSON.parse(new TextDecoder().decode(metaBytes))
        const jpegBytes = new Uint8Array(buffer, 4 + metaLen)

        const blob = new Blob([jpegBytes], { type: 'image/jpeg' })
        const url = URL.createObjectURL(blob)

        const cam = cameras.value.find(c => c.id === cameraId)
        if (cam) {
          // 释放旧 blob URL 避免内存泄漏
          if (cam._blobUrl) URL.revokeObjectURL(cam._blobUrl)
          cam._blobUrl = url
          cam.snapshotUrl = url
          cam.snapshot = null  // 清掉旧 base64，优先用 URL
          cam.total_persons = meta.total_persons ?? 0
          cam.persons = meta.persons ?? []
          cam.unknown_persons = cam.total_persons - (cam.persons?.filter(p => !p.is_unknown).length || 0)
        }
        return
      }

      // 兼容旧 JSON 帧（降级路径）
      const data = JSON.parse(event.data)
      if (data.type === 'frame' && data.image_base64) {
        const cam = cameras.value.find(c => c.id === cameraId)
        if (cam) {
          cam.snapshot = data.image_base64
          cam.snapshotUrl = null
          cam.total_persons = data.total_persons
          cam.persons = data.persons
          cam.unknown_persons = data.total_persons - (data.persons?.filter(p => !p.is_unknown).length || 0)
        }
      }
    } catch (e) {
      console.error(`[视频流] 解析错误 [${cameraId}]:`, e)
    }
  }

  camWs.onclose = () => {
    console.log(`[视频流] 断开: ${cameraId}，5s后重连`)
    const cam = cameras.value.find(c => c.id === cameraId)
    if (cam) showToast(`「${cam.name}」视频流已断开，正在自动重连...`, 'error')
    delete cameraWsMap[cameraId]
    // 自动重连（仅当摄像头仍在运行）
    setTimeout(() => {
      const cam = cameras.value.find(c => c.id === cameraId)
      if (cam && cam.running) connectCameraStream(cameraId)
    }, 5000)
  }

  camWs.onerror = () => {
    // onclose 会紧随触发，不重复处理
  }

  cameraWsMap[cameraId] = camWs
}

function disconnectCameraStream(cameraId) {
  const camWs = cameraWsMap[cameraId]
  if (camWs) {
    camWs.onclose = null   // 阻止自动重连
    camWs.close()
    delete cameraWsMap[cameraId]
  }
  // 清理对应的 blob URL
  const cam = cameras.value.find(c => c.id === cameraId)
  if (cam) {
    if (cam._blobUrl) {
      URL.revokeObjectURL(cam._blobUrl)
      cam._blobUrl = null
    }
    cam.snapshotUrl = null
  }
}

async function deleteCameraConfirm(id, name) {
  const ok = await showConfirm('删除摄像头', `确定要删除「${name}」吗？此操作不可撤销。`, null)
  if (!ok) return
  try {
    await axios.delete(`/api/camera/${id}`)
    showToast(`摄像头「${name}」已删除`, 'success')
    await loadCameras()
    await loadCameraDatabase()
  } catch (e) {
    showToast('删除失败: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

function openEditCamera(camera) {
  editingCamera.value = {
    id: camera.id,
    name: camera.name,
    source: camera.source || '',
    location: camera.location || '',
    fps: camera.fps || 15,
    rotation: camera.rotation || 0,
  }
  showEditCamera.value = true
}

async function updateCamera() {
  try {
    await axios.put(`/api/camera/${editingCamera.value.id}`, {
      id: editingCamera.value.id,
      name: editingCamera.value.name,
      source: editingCamera.value.source,
      location: editingCamera.value.location,
      fps: editingCamera.value.fps,
      rotation: editingCamera.value.rotation,
    })
    showEditCamera.value = false
    showToast('摄像头配置已更新', 'success')
    await loadCameras()
    await loadCameraDatabase()
  } catch (e) {
    showToast('修改失败: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

// ========== 识别记录 ==========
async function loadRecordsSummary() {
  try {
    const res = await axios.get('/api/records/summary')
    recordsSummary.value = res.data
  } catch (e) {
    console.error('加载统计失败:', e)
  }
}

async function loadRecords(page = 1) {
  loading.value.records = true
  recordsPage.value = page
  const params = new URLSearchParams()
  params.set('page', String(page))
  params.set('page_size', '20')
  if (recordsFilter.value.person_name) params.set('person_name', recordsFilter.value.person_name)
  if (recordsFilter.value.start_time) params.set('start_time', recordsFilter.value.start_time)
  if (recordsFilter.value.end_time) params.set('end_time', recordsFilter.value.end_time)
  if (recordsFilter.value.record_type) params.set('record_type', recordsFilter.value.record_type)

  try {
    const res = await axios.get(`/api/records?${params.toString()}`)
    strangerCounter.clear()
    recordsList.value = res.data.records || []
    recordsTotal.value = res.data.total || 0
    recordsTotalPages.value = res.data.total_pages || 1
  } catch (e) {
    console.error('加载记录失败:', e)
  } finally {
    loading.value.records = false
  }
}

function exportRecordsCSV() {
  const data = recordsList.value
  if (data.length === 0) {
    showToast('暂无记录可导出', 'info')
    return
  }
  const headers = ['时间', '摄像头', '姓名', '置信度(%)', '类型', '是否陌生人']
  const rows = data.map(r => [
    formatDate(r.detected_at),
    r.camera_id || '',
    r.person_name || (r.is_unknown ? '陌生人' : ''),
    r.confidence != null ? Math.round(r.confidence) : '',
    r.is_unknown ? '陌生人' : '已知',
    r.is_unknown ? '是' : '否',
  ])
  // CSV 转义
  const escapeCsv = (v) => {
    const s = String(v)
    if (s.includes(',') || s.includes('"') || s.includes('\n')) {
      return '"' + s.replace(/"/g, '""') + '"'
    }
    return s
  }
  const csv = [headers.join(','), ...rows.map(r => r.map(escapeCsv).join(','))].join('\n')
  const bom = '\uFEFF'
  const blob = new Blob([bom + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `识别记录_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
  showToast(`已导出 ${data.length} 条记录`, 'success')
}

function debounceSearch() {
  clearTimeout(recordsDebounceTimer)
  recordsDebounceTimer = setTimeout(() => loadRecords(1), 400)
}

function resetRecordsFilter() {
  recordsFilter.value.person_name = ''
  recordsFilter.value.start_time = ''
  recordsFilter.value.end_time = ''
  recordsFilter.value.record_type = ''
  loadRecords(1)
  loadRecordsSummary()
}

async function clearAllRecords() {
  const ok = await showConfirm('清空记录', '确定要清空全部识别记录吗？此操作不可撤销！')
  if (!ok) return
  try {
    const res = await axios.delete('/api/records/clear')
    showToast(res.data.message, 'success')
    recordsList.value = []
    recordsTotal.value = 0
    recordsTotalPages.value = 1
    loadRecordsSummary()
  } catch (e) {
    showToast('清空失败: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

// ========== 人像库 ==========
async function loadPersons() {
  loading.value.persons = true
  try {
    const res = await axios.get('/api/persons')
    personList.value = res.data.persons || []
    filteredPersons.value = [...personList.value]
  } catch (e) {
    console.error('加载人像库失败:', e)
  } finally {
    loading.value.persons = false
  }
}

function filterPersonList() {
  const kw = personSearch.value.toLowerCase()
  filteredPersons.value = personList.value.filter(p =>
    !kw || p.name.toLowerCase().includes(kw) ||
    (p.department || '').toLowerCase().includes(kw) ||
    (p.category || '').toLowerCase().includes(kw)
  )
}

function categoryLabel(cat) {
  const map = { staff: '员工', visitor: '访客', blacklist: '黑名单' }
  return map[cat] || cat || '未知'
}

// ========== 人像库 — 注册 ==========
function resetRegisterForm() {
  registerForm.value = { name: '', category: 'staff', department: '', files: [] }
}

function onRegisterFileChange(e) {
  registerForm.value.files = Array.from(e.target.files)
}

function onRegisterDrop(e) {
  registerForm.value.files = Array.from(e.dataTransfer.files)
}

async function registerPerson() {
  const fd = new FormData()
  fd.append('name', registerForm.value.name)
  fd.append('category', registerForm.value.category)
  fd.append('department', registerForm.value.department)
  registerForm.value.files.forEach(f => fd.append('images', f))

  try {
    const res = await axios.post('/api/persons/register', fd)
    showToast(res.data.message, 'success')
    showRegisterPerson.value = false
    resetRegisterForm()
    await loadPersons()
  } catch (e) {
    showToast('注册失败: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

// ========== 人像库 — 追加照片 ==========
function openAddPhoto(name) {
  addPhotoTarget.value = name
  addPhotoFiles.value = []
  showAddPhoto.value = true
}

function onAddPhotoFileChange(e) {
  addPhotoFiles.value = Array.from(e.target.files)
}

function onAddPhotoDrop(e) {
  addPhotoFiles.value = Array.from(e.dataTransfer.files)
}

async function addPhoto() {
  const fd = new FormData()
  addPhotoFiles.value.forEach(f => fd.append('images', f))

  try {
    const res = await axios.post(`/api/persons/${addPhotoTarget.value}/add-photo`, fd)
    showToast(res.data.message, 'success')
    showAddPhoto.value = false
    addPhotoFiles.value = []
    await loadPersons()
  } catch (e) {
    showToast('追加失败: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

// ========== 人像库 — 删除 ==========
async function deletePersonConfirm(name) {
  const ok = await showConfirm('删除人员', `确定要删除「${name}」吗？此操作不可撤销。`)
  if (!ok) return

  try {
    await axios.delete(`/api/persons/${name}`)
    showToast(`已删除 ${name}`, 'success')
    await loadPersons()
  } catch (e) {
    showToast('删除失败: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

// ========== 人像库 — 头像悬浮预览 ==========
async function fetchAvatar(name, event) {
  // 缓存命中
  if (avatarCache.value[name]) {
    showAvatarPreview(event, 'data:image/jpeg;base64,' + avatarCache.value[name])
    return
  }
  // 先显示加载态
  showAvatarPreview(event, '')
  try {
    const res = await axios.get(`/api/persons/${name}/avatar`)
    avatarCache.value[name] = res.data.avatar_base64
    avatarPreview.value.src = 'data:image/jpeg;base64,' + res.data.avatar_base64
  } catch {
    avatarPreview.value.src = ''
  }
}

function showAvatarPreview(event, src) {
  const rect = event.target.getBoundingClientRect()
  const previewW = 168, previewH = 190
  let x = rect.right + 8
  let y = rect.top - 60
  // 右侧边界：超出屏幕则弹到左侧
  if (x + previewW > window.innerWidth - 12) x = rect.left - previewW - 8
  // 下边界
  if (y + previewH > window.innerHeight - 12) y = window.innerHeight - previewH - 12
  // 上边界
  if (y < 8) y = 8
  avatarPreview.value = { visible: true, x, y, src }
}

function hideAvatarPreview() {
  avatarPreview.value.visible = false
}

async function fetchSnapshot(recordId, event) {
  if (snapshotCache.value[recordId]) {
    showAvatarPreview(event, 'data:image/jpeg;base64,' + snapshotCache.value[recordId])
    return
  }
  showAvatarPreview(event, '')
  try {
    const res = await axios.get(`/api/records/snapshot/${recordId}`)
    snapshotCache.value[recordId] = res.data.snapshot_base64
    avatarPreview.value.src = 'data:image/jpeg;base64,' + res.data.snapshot_base64
  } catch {
    avatarPreview.value.src = ''
  }
}

function formatDate(iso) {
  if (!iso) return '--'
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { hour12: false })
  } catch { return iso }
}

// 陌生人编号缓存：{(camera_id, hour_window) => 编号}
const strangerCounter = new Map()
function getPersonDisplayName(r) {
  if (!r.is_unknown) return r.person_name
  // 按摄像头 + 小时窗口编号
  const ts = r.detected_at ? new Date(r.detected_at) : new Date()
  const hourKey = `${ts.getFullYear()}${(ts.getMonth()+1).toString().padStart(2,'0')}${ts.getDate().toString().padStart(2,'0')}${ts.getHours().toString().padStart(2,'0')}`
  const camId = r.camera_id || 'unknown'
  const key = `${camId}_${hourKey}`
  if (!strangerCounter.has(key)) strangerCounter.set(key, strangerCounter.size + 1)
  const n = strangerCounter.get(key)
  const timeLabel = `${String(ts.getHours()).padStart(2,'0')}:${String(ts.getMinutes()).padStart(2,'0')}`
  return `陌生人#${n} (${camId} ${timeLabel})`
}

// ========== 摄像头库（数据表格） ==========

async function loadCameraDatabase() {
  loading.value.cameraDB = true
  try {
    const res = await axios.get('/api/camera/database')
    cameraDBList.value = res.data.cameras || []
    filteredCameraDB.value = [...cameraDBList.value]
  } catch (e) {
    console.error('加载摄像头库失败:', e)
  } finally {
    loading.value.cameraDB = false
  }
}

function filterCameraDBList() {
  const kw = cameraDBSearch.value.toLowerCase()
  const st = cameraDBStatusFilter.value
  filteredCameraDB.value = cameraDBList.value.filter(c => {
    const matchSearch = !kw ||
      c.name.toLowerCase().includes(kw) ||
      c.id.toLowerCase().includes(kw) ||
      (c.location || '').toLowerCase().includes(kw)
    const matchStatus = !st || c.status === st
    return matchSearch && matchStatus
  })
}

function toggleDarkMode() {
  isDark.value = !isDark.value
  localStorage.setItem('vision-monitor-theme', isDark.value ? 'dark' : 'light')
}

// ========== 生命周期 ==========
let refreshTimer = null

onMounted(async () => {
  // 恢复主题设置
  const savedTheme = localStorage.getItem('vision-monitor-theme')
  if (savedTheme) isDark.value = savedTheme === 'dark'
  else isDark.value = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? true

  // 恢复聊天历史
  loadMessages()

  connectWebSocket()
  await loadCameras()
  // 首次加载后立即获取快照
  await refreshSnapshot()
  // 启动时自动将所有摄像头 FPS 更新为 15（修复老数据 fps=5 的问题）
  axios.post('/api/camera/update-fps', null, { params: { fps: 15 } }).catch(() => {})
  // 为所有已运行的摄像头建立实时 WebSocket 流
  cameras.value.forEach(cam => {
    if (cam.running) connectCameraStream(cam.id)
  })
  addMessage('assistant', '你好！我是智能监控助手。\n\n我可以帮你：\n• 查看实时监控画面\n• 查询人员出入记录\n• 统计分析数据\n• 管理人像库\n\n请随时向我提问！')

  // 定时刷新（解耦：loadCameras 和 refreshSnapshot 并行，互不阻塞）
  refreshTimer = setInterval(() => {
    loadCameras(false)       // 后台静默刷新，不显示骨架屏（避免闪烁）
    refreshSnapshot()       // 独立执行，不等待 loadCameras
  }, 3000)
})

onBeforeUnmount(() => {
  if (ws) ws.close()
  if (refreshTimer) clearInterval(refreshTimer)
  // 关闭所有摄像头 WebSocket 流 + 清理 blob URL
  Object.keys(cameraWsMap).forEach(id => disconnectCameraStream(id))
  // 兜底清理所有 blob URL
  cameras.value.forEach(c => {
    if (c._blobUrl) URL.revokeObjectURL(c._blobUrl)
  })
})
</script>

<style>
/* ========== 全局主题变量 ========== */
:root {
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --bg-input: #0f172a;
  --bg-header: #1e293b;
  --bg-chat: #1a2332;
  --bg-hover: rgba(59, 130, 246, 0.04);
  --border-primary: #334155;
  --border-secondary: #1e293b;
  --text-primary: #e2e8f0;
  --text-secondary: #f1f5f9;
  --text-muted: #94a3b8;
  --text-dim: #64748b;
  --text-dim2: #475569;
  --accent: #3b82f6;
  --accent-hover: #2563eb;
  --accent-light: #60a5fa;
  --green: #22c55e;
  --green-bg: rgba(34, 197, 94, 0.15);
  --red: #ef4444;
  --red-bg: rgba(239, 68, 68, 0.15);
  --shadow: rgba(0, 0, 0, 0.5);
  color-scheme: dark;
}

[data-theme="light"] {
  --bg-primary: #f1f5f9;
  --bg-secondary: #ffffff;
  --bg-input: #f8fafc;
  --bg-header: #ffffff;
  --bg-chat: #f8fafc;
  --bg-hover: rgba(59, 130, 246, 0.06);
  --border-primary: #cbd5e1;
  --border-secondary: #e2e8f0;
  --text-primary: #1e293b;
  --text-secondary: #0f172a;
  --text-muted: #64748b;
  --text-dim: #94a3b8;
  --text-dim2: #94a3b8;
  --accent: #3b82f6;
  --accent-hover: #2563eb;
  --accent-light: #2563eb;
  --green: #16a34a;
  --green-bg: rgba(22, 163, 74, 0.1);
  --red: #dc2626;
  --red-bg: rgba(220, 38, 38, 0.1);
  --shadow: rgba(0, 0, 0, 0.15);
  color-scheme: light;
}
</style>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

/* ========== Header ========== */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: #1e293b;
  border-bottom: 1px solid #334155;
  flex-shrink: 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo-icon {
  font-size: 24px;
  display: flex;
  align-items: center;
  color: #3b82f6;
}

.logo h1 {
  font-size: 18px;
  font-weight: 600;
  color: #f1f5f9;
}

.badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 12px;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  color: white;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #94a3b8;
}

.connection-status .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ef4444;
}

.connection-status.connected .dot {
  background: #22c55e;
}

/* ========== Main Content ========== */
.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  gap: 0;
}

/* ========== Monitor Panel ========== */
.monitor-panel {
  width: 55%;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #334155;
  background: #0f172a;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #1e293b;
  flex-shrink: 0;
}

.panel-header h2 {
  font-size: 16px;
  font-weight: 600;
}

.panel-actions {
  display: flex;
  gap: 8px;
}

.camera-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}

.camera-card {
  background: #1e293b;
  border-radius: 12px;
  overflow: hidden;
  border: 2px solid #334155;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.camera-card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.2);
}

.camera-card.active {
  border-color: #22c55e;
}

.camera-feed {
  position: relative;
  aspect-ratio: 16/10;
  background: #0f172a;
  overflow: hidden;
}

.camera-feed img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transform-origin: center center;
}

.no-signal {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #475569;
  gap: 8px;
}

.no-signal-svg {
  opacity: 0.35;
}
.tab-icon {
  display: inline-block;
  vertical-align: -2px;
  margin-right: 4px;
}
.btn-icon-inline {
  display: inline-block;
  vertical-align: -1px;
  margin-right: 3px;
}
.inline-icon {
  display: inline-block;
  vertical-align: -1px;
  margin-right: 4px;
  opacity: 0.7;
}
.person-count-icon {
  display: inline-block;
  vertical-align: -2px;
  margin-right: 2px;
}
/* 头像占位符 */
.thumb-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: #475569;
}
/* 状态圆点指示器 */
.status-indicator {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  vertical-align: middle;
  margin-right: 3px;
}
.status-indicator.online-dot { background: #22c55e; box-shadow: 0 0 4px rgba(34,197,94,0.5); }
.status-indicator.offline-dot { background: #ef4444; }

/* 右上角人数 */
.camera-overlay {
  position: absolute;
  top: 8px;
  right: 8px;
}

.person-count {
  background: rgba(0, 0, 0, 0.7);
  color: #e2e8f0;
  padding: 4px 10px;
  border-radius: 16px;
  font-size: 13px;
}

/* 底部浮层：左信息 + 右按钮 */
.camera-footer {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding: 12px 12px 10px;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.75));
}

.camera-meta { color: #e2e8f0; }

.camera-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 14px;
}

.camera-location { font-size: 12px; opacity: 0.7; margin-top: 2px; }
.camera-fps { font-size: 11px; opacity: 0.5; margin-top: 2px; }

.status-dot { width: 8px; height: 8px; border-radius: 50%; }
.status-dot.online { background: #22c55e; box-shadow: 0 0 6px #22c55e; }
.status-dot.offline { background: #ef4444; }

.camera-actions { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.rotation-group { display: flex; gap: 2px; background: rgba(255,255,255,0.08); border-radius: 6px; padding: 2px; }
.btn-rot {
  min-width: 32px; padding: 2px 6px; font-size: 11px;
  background: transparent; color: #94a3b8; border: none; border-radius: 4px; cursor: pointer;
}
.btn-rot:hover { background: rgba(255,255,255,0.12); color: #e2e8f0; }
.btn-rot.active { background: #3b82f6; color: #fff; }

/* ========== Chat Panel ========== */
.chat-panel {
  width: 45%;
  display: flex;
  flex-direction: column;
  background: #1a2332;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message {
  display: flex;
  gap: 10px;
  animation: fadeIn 0.3s ease-out;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
  background: #1e293b;
}

.message.user .message-avatar {
  background: #3b82f6;
}

.message-content {
  max-width: 80%;
}

.message.user .message-content {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.message-bubble {
  padding: 10px 14px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.message.assistant .message-bubble {
  background: #1e293b;
  border-bottom-left-radius: 4px;
}

.message.user .message-bubble {
  background: #3b82f6;
  border-bottom-right-radius: 4px;
  color: white;
}

.message-bubble.typing {
  padding: 14px 20px;
}

.typing-dots {
  display: flex;
  gap: 4px;
}

.typing-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #64748b;
  animation: pulse-dot 1.4s infinite;
}

.typing-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

.message-time {
  font-size: 11px;
  color: #475569;
  margin-top: 4px;
}

.message-bubble :deep(code) {
  background: rgba(59, 130, 246, 0.15);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}

.message-bubble :deep(strong) {
  color: #60a5fa;
}

/* ========== Quick Commands ========== */
.quick-commands {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 20px 12px;
}

.quick-cmd {
  padding: 6px 14px;
  border-radius: 20px;
  border: 1px solid #334155;
  background: #1e293b;
  color: #94a3b8;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.quick-cmd:hover {
  border-color: #3b82f6;
  color: #60a5fa;
  background: rgba(59, 130, 246, 0.1);
}

/* ========== Chat Input ========== */
.chat-input-area {
  display: flex;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid #334155;
  background: #1e293b;
}

.chat-input-area textarea {
  flex: 1;
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid #334155;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 14px;
  resize: none;
  outline: none;
  transition: border-color 0.2s;
  font-family: inherit;
}

.chat-input-area textarea:focus {
  border-color: #3b82f6;
}

.chat-input-area textarea::placeholder {
  color: #475569;
}

/* ========== Buttons ========== */
.btn {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid #334155;
  background: #1e293b;
  color: #e2e8f0;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn:hover {
  background: #334155;
  border-color: #475569;
}
.btn:active {
  transform: scale(0.97);
}

.btn-primary {
  background: #3b82f6;
  border-color: #3b82f6;
  color: white;
}

.btn-primary:hover {
  background: #2563eb;
  box-shadow: 0 2px 8px rgba(37,99,235,0.3);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
}

.btn-xs {
  padding: 3px 8px;
  font-size: 11px;
  border-radius: 6px;
}

.btn-success {
  background: #22c55e;
  border-color: #22c55e;
  color: white;
}

.btn-success:hover {
  background: #16a34a;
  box-shadow: 0 2px 8px rgba(22,163,74,0.3);
}

.btn-danger {
  background: #ef4444;
  border-color: #ef4444;
  color: white;
}

.btn-danger:hover {
  background: #dc2626;
  box-shadow: 0 2px 8px rgba(220,38,38,0.3);
}

.btn-icon {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  padding: 6px;
  border-radius: 8px;
  color: #94a3b8;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.btn-icon:hover {
  background: rgba(148,163,184,0.1);
  color: #e2e8f0;
}

.send-btn {
  padding: 8px 14px;
  font-size: 18px;
  align-self: flex-end;
}

/* ========== Empty State ========== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: #64748b;
  gap: 8px;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 8px;
}

/* ========== Modal ========== */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal {
  background: #1e293b;
  border-radius: 16px;
  padding: 24px;
  width: 420px;
  border: 1px solid #334155;
}

.modal h3 {
  font-size: 18px;
  margin-bottom: 20px;
}

.form-group {
  margin-bottom: 14px;
}

.form-group label {
  display: block;
  font-size: 13px;
  color: #94a3b8;
  margin-bottom: 6px;
}

.form-group input {
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #334155;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 14px;
  outline: none;
}

.form-group input:focus {
  border-color: #3b82f6;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}

/* ========== Utility ========== */
.text-xs { font-size: 12px; }
.text-sm { font-size: 13px; }
.text-slate-500 { color: #64748b; }
.text-yellow-400 { color: #facc15; }

/* ========== Tabs ========== */
.tabs {
  display: flex;
  gap: 4px;
}
.tab-btn {
  padding: 8px 18px;
  border-radius: 8px 8px 0 0;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border-bottom: 2px solid transparent;
}
.tab-btn:hover { color: #94a3b8; background: rgba(148,163,184,0.06); }
.tab-btn.active {
  color: #e2e8f0;
  background: #1e293b;
  border-bottom-color: #3b82f6;
}
.tab-btn svg {
  vertical-align: -2px;
}

/* ========== Data Panel (人像库/摄像头库) ========== */
.data-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.search-bar {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid #1e293b;
}
.search-input {
  flex: 1;
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid #334155;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s;
}
.search-input:focus { border-color: #3b82f6; }
.search-select {
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid #334155;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 13px;
  outline: none;
  cursor: pointer;
}
.table-wrap {
  flex: 1;
  overflow-y: auto;
  padding: 0 16px;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.data-table th {
  padding: 10px 12px;
  text-align: left;
  color: #64748b;
  font-weight: 600;
  border-bottom: 1px solid #1e293b;
  position: sticky;
  top: 0;
  background: #0f172a;
  z-index: 1;
  white-space: nowrap;
}
.data-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #1a2332;
  white-space: nowrap;
}
.data-table tbody tr:hover { background: rgba(59, 130, 246, 0.06); transition: background 0.15s; }
.table-summary {
  padding: 8px 16px;
  font-size: 12px;
  color: #475569;
  border-top: 1px solid #1e293b;
  flex-shrink: 0;
}
.empty-state-small {
  text-align: center;
  padding: 40px;
  color: #475569;
}

/* ========== 标签/徽章 ========== */
.badge-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 500;
}
.badge-tag.staff     { background: rgba(59, 130, 246, 0.15); color: #60a5fa; }
.badge-tag.visitor   { background: rgba(168, 85, 247, 0.15); color: #a78bfa; }
.badge-tag.blacklist { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.badge-tag.online    { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
.badge-tag.offline   { background: rgba(239, 68, 68, 0.15); color: #f87171; }

.code-tag {
  background: #0f172a;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #60a5fa;
}

/* ========== 一键跳转按钮 ========== */
.btn-jump {
  background: linear-gradient(135deg, #8b5cf6, #6366f1);
  border-color: transparent;
  color: white;
}
.btn-jump:hover {
  background: linear-gradient(135deg, #7c3aed, #4f46e5);
  box-shadow: 0 2px 10px rgba(139, 92, 246, 0.35);
}

/* ========== 头像 ========== */
.avatar-cell { cursor: pointer; display: inline-block; }
.avatar-thumb {
  width: 36px; height: 36px;
  border-radius: 50%;
  overflow: hidden;
  display: flex; align-items: center; justify-content: center;
  background: #0f172a;
  border: 2px solid #334155;
  transition: border-color 0.2s;
  font-size: 18px;
}
.avatar-thumb:hover { border-color: #3b82f6; }
.avatar-thumb img { width: 100%; height: 100%; object-fit: cover; }

.avatar-preview {
  position: fixed;
  z-index: 200;
  width: 160px; height: 180px;
  border-radius: 12px;
  overflow: hidden;
  border: 2px solid #3b82f6;
  background: #0f172a;
  box-shadow: 0 8px 30px rgba(0,0,0,0.6);
  display: flex; align-items: center; justify-content: center;
  color: #64748b;
  font-size: 13px;
}
.avatar-preview img { width: 100%; height: 100%; object-fit: cover; }

/* ========== 文件上传区域 ========== */
.file-upload-zone {
  border: 2px dashed #334155;
  border-radius: 10px;
  padding: 24px;
  text-align: center;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
}
.file-upload-zone:hover {
  border-color: #3b82f6;
  color: #94a3b8;
  background: rgba(59,130,246,0.05);
}

.form-select {
  width: 100%;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #334155;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 14px;
  outline: none;
  cursor: pointer;
}
.form-select:focus { border-color: #3b82f6; }

/* ========== 操作列 / 颜色标记 ========== */
.action-cell { display: flex; gap: 4px; }
.text-green { color: #4ade80; font-weight: 600; }
.text-yellow { color: #facc15; }
.text-red { color: #ef4444; font-weight: 600; }
.text-muted { color: #64748b; }

/* ========== 统计卡片 ========== */
.stats-row {
  display: flex; gap: 12px;
  margin-bottom: 12px;
}
.stat-card {
  flex: 1;
  background: #1e293b;
  border-radius: 10px;
  padding: 14px 16px;
  text-align: center;
  border: 1px solid #334155;
}
.stat-card.green { border-color: #16a34a; }
.stat-card.orange { border-color: #ea580c; }
.stat-value { font-size: 28px; font-weight: 700; color: #e2e8f0; }
.stat-label { font-size: 12px; color: #64748b; margin-top: 4px; }

/* 错误提示 */
.error-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #7f1d1d;
  color: #fca5a5;
  padding: 10px 14px;
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 13px;
}
.error-dismiss {
  background: none;
  border: none;
  color: #fca5a5;
  cursor: pointer;
  font-size: 16px;
  padding: 0 4px;
}
.error-dismiss:hover { color: #fff; }

/* ========== 分页 ========== */
.pagination {
  display: flex; align-items: center; justify-content: center;
  gap: 16px; padding: 12px 0;
}
.page-info { color: #94a3b8; font-size: 13px; }

/* ========== 已知/陌生人徽章 ========== */
.badge-tag.known { background: rgba(16,185,129,0.15); color: #10b981; }
.badge-tag.unknown { background: rgba(245,158,11,0.15); color: #f59e0b; }

/* ========== 聚合视图 ========== */
.group-row:hover {
  background: rgba(59, 130, 246, 0.08) !important;
}
.group-row td {
  padding: 10px 12px;
}
.expand-icon {
  font-size: 10px;
  color: #64748b;
  transition: transform 0.2s;
}
.group-count {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
  font-size: 12px;
  font-weight: 600;
}
.expanded-panel {
  background: #0c1520;
  border-top: 1px solid #1e293b;
  border-bottom: 1px solid #1e293b;
  padding: 8px 16px 8px 32px;
}
.expanded-panel .sub-table th {
  background: #0c1520;
  font-size: 11px;
  padding: 6px 10px;
}
.expanded-panel .sub-table td {
  font-size: 12px;
  padding: 6px 10px;
}

/* ========== Toast 通知 ========== */
.toast-container {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 300;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.toast-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  box-shadow: 0 8px 30px rgba(0,0,0,0.5);
  animation: toastIn 0.3s ease-out, toastOut 0.3s ease-in 2.5s forwards;
  max-width: 500px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.toast-item.success { background: #065f46; color: #6ee7b7; border: 1px solid #059669; }
.toast-item.error   { background: #7f1d1d; color: #fca5a5; border: 1px solid #dc2626; }
.toast-item.info    { background: #1e293b; color: #94a3b8; border: 1px solid #475569; }
.toast-icon { font-size: 18px; flex-shrink: 0; }
@keyframes toastIn {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes toastOut {
  from { opacity: 1; transform: translateY(0); }
  to { opacity: 0; transform: translateY(-10px); }
}

/* ========== Confirm 弹窗 ========== */
.confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 250;
  animation: fadeIn 0.2s ease-out;
}
.confirm-modal {
  background: #1e293b;
  border-radius: 16px;
  padding: 28px 28px 20px;
  max-width: 420px;
  width: 90%;
  border: 1px solid #334155;
  text-align: center;
}
.confirm-modal .confirm-icon {
  font-size: 44px;
  margin-bottom: 12px;
}
.confirm-modal h3 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 8px;
  color: #e2e8f0;
}
.confirm-modal p {
  font-size: 14px;
  color: #94a3b8;
  line-height: 1.6;
  margin-bottom: 20px;
}
.confirm-actions {
  display: flex;
  gap: 10px;
  justify-content: center;
}
.confirm-actions .btn {
  min-width: 90px;
}

/* ========== Loading 骨架屏 ========== */
.skeleton-row {
  height: 36px;
  background: linear-gradient(90deg, #1e293b 25%, #334155 50%, #1e293b 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  border-radius: 6px;
  margin-bottom: 6px;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.loading-wrap {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 16px;
}

/* ========== 人数详情弹窗 ========== */
.badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
}
.badge-known { background: #064e3b; color: #6ee7b7; }
.badge-unknown { background: #7f1d1d; color: #fca5a5; }
.row-unknown td { color: #fca5a5; }
.person-count { cursor: pointer; }
.person-count:hover { color: #60a5fa; }
.sort-select {
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid #334155;
  background: #1e293b;
  color: #e2e8f0;
  font-size: 13px;
  cursor: pointer;
}
.sortable { cursor: pointer; user-select: none; }
.sortable:hover { color: var(--accent-light); }

/* ========== 亮色主题覆盖 ========== */
[data-theme="light"] .header { background: #fff; border-bottom-color: #e2e8f0; }
[data-theme="light"] .logo h1 { color: #1e293b; }
[data-theme="light"] .connection-status { color: #64748b; }
[data-theme="light"] .monitor-panel { background: #f8fafc; border-right-color: #e2e8f0; }
[data-theme="light"] .panel-header { border-bottom-color: #e2e8f0; }
[data-theme="light"] .chat-panel { background: #f1f5f9; }
[data-theme="light"] .chat-messages { background: #f8fafc; }
[data-theme="light"] .chat-input-area { background: #fff; border-top-color: #e2e8f0; }
[data-theme="light"] .chat-input-area textarea { background: #f1f5f9; border-color: #cbd5e1; color: #1e293b; }
[data-theme="light"] .chat-input-area textarea::placeholder { color: #94a3b8; }
[data-theme="light"] .camera-card { background: #fff; border-color: #e2e8f0; }
[data-theme="light"] .camera-grid { background: #f1f5f9; }
[data-theme="light"] .camera-feed { background: #f1f5f9; }
[data-theme="light"] .no-signal { color: #94a3b8; }
[data-theme="light"] .camera-meta { color: #fff; }
[data-theme="light"] .data-table th { background: #f8fafc; border-bottom-color: #e2e8f0; color: #64748b; }
[data-theme="light"] .data-table td { border-bottom-color: #f1f5f9; }
[data-theme="light"] .data-table tbody tr:hover { background: rgba(59,130,246,0.04); }
[data-theme="light"] .table-summary { border-top-color: #e2e8f0; }
[data-theme="light"] .search-bar { border-bottom-color: #e2e8f0; }
[data-theme="light"] .search-input { background: #fff; border-color: #cbd5e1; color: #1e293b; }
[data-theme="light"] .search-select { background: #fff; border-color: #cbd5e1; color: #1e293b; }
[data-theme="light"] .tab-btn.active { background: #fff; color: #1e293b; }
[data-theme="light"] .tab-btn { color: #64748b; }
[data-theme="light"] .tab-btn:hover { color: #1e293b; }
[data-theme="light"] .btn { background: #f1f5f9; border-color: #cbd5e1; color: #1e293b; }
[data-theme="light"] .btn:hover { background: #e2e8f0; }
[data-theme="light"] .btn-primary { background: #3b82f6; border-color: #3b82f6; color: #fff; }
[data-theme="light"] .btn-primary:hover { background: #2563eb; }
[data-theme="light"] .btn-success { background: #22c55e; border-color: #22c55e; color: #fff; }
[data-theme="light"] .btn-danger { background: #ef4444; border-color: #ef4444; color: #fff; }
[data-theme="light"] .btn-rot { color: #64748b; }
[data-theme="light"] .btn-rot:hover { background: rgba(0,0,0,0.06); color: #1e293b; }
[data-theme="light"] .rotation-group { background: rgba(0,0,0,0.06); }
[data-theme="light"] .modal { background: #fff; border-color: #e2e8f0; }
[data-theme="light"] .modal h3 { color: #1e293b; }
[data-theme="light"] .form-group label { color: #64748b; }
[data-theme="light"] .form-group input { background: #f8fafc; border-color: #cbd5e1; color: #1e293b; }
[data-theme="light"] .form-select { background: #f8fafc; border-color: #cbd5e1; color: #1e293b; }
[data-theme="light"] .confirm-modal { background: #fff; border-color: #e2e8f0; }
[data-theme="light"] .confirm-modal h3 { color: #1e293b; }
[data-theme="light"] .confirm-modal p { color: #64748b; }
[data-theme="light"] .stat-card { background: #fff; border-color: #e2e8f0; }
[data-theme="light"] .stat-value { color: #1e293b; }
[data-theme="light"] .message.assistant .message-bubble { background: #e2e8f0; color: #1e293b; }
[data-theme="light"] .message-avatar { background: #e2e8f0; }
[data-theme="light"] .quick-cmd { background: #e2e8f0; border-color: #cbd5e1; color: #64748b; }
[data-theme="light"] .quick-cmd:hover { background: rgba(59,130,246,0.1); color: #3b82f6; }
[data-theme="light"] .code-tag { background: #f1f5f9; color: #3b82f6; }
[data-theme="light"] .avatar-thumb { background: #f1f5f9; }
[data-theme="light"] .expanded-panel { background: #f1f5f9; border-color: #e2e8f0; }
[data-theme="light"] .expanded-panel .sub-table th { background: #f1f5f9; }
[data-theme="light"] .skeleton-row { background: linear-gradient(90deg,#e2e8f0 25%,#cbd5e1 50%,#e2e8f0 75%); background-size: 200% 100%; }
[data-theme="light"] .file-upload-zone { border-color: #cbd5e1; color: #94a3b8; }
[data-theme="light"] .file-upload-zone:hover { border-color: #3b82f6; color: #64748b; background: rgba(59,130,246,0.04); }
[data-theme="light"] .sort-select { background: #fff; border-color: #cbd5e1; color: #1e293b; }
[data-theme="light"] .toast-item.info { background: #fff; color: #64748b; border-color: #cbd5e1; }
[data-theme="light"] .empty-state-small { color: #94a3b8; }
[data-theme="light"] .text-slate-500 { color: #94a3b8; }
[data-theme="light"] .message-bubble :deep(strong) { color: #3b82f6; }
[data-theme="light"] .modal-overlay { background: rgba(0,0,0,0.4); }
[data-theme="light"] .confirm-overlay { background: rgba(0,0,0,0.4); }
[data-theme="light"] .badge-known { background: #dcfce7; color: #16a34a; }
[data-theme="light"] .badge-unknown { background: #fef2f2; color: #dc2626; }
[data-theme="light"] .row-unknown td { color: #dc2626; }
[data-theme="light"] .badge-tag.staff { background: rgba(59,130,246,0.1); }
[data-theme="light"] .badge-tag.visitor { background: rgba(168,85,247,0.1); }
[data-theme="light"] .badge-tag.blacklist { background: rgba(239,68,68,0.1); }
[data-theme="light"] .badge-tag.online { background: rgba(34,197,94,0.1); }
[data-theme="light"] .badge-tag.offline { background: rgba(239,68,68,0.1); }
[data-theme="light"] .badge-tag.known { background: rgba(16,185,129,0.1); }
[data-theme="light"] .badge-tag.unknown { background: rgba(245,158,11,0.1); }
[data-theme="light"] .group-count { background: rgba(59,130,246,0.1); }
[data-theme="light"] .error-alert { background: #fef2f2; color: #dc2626; }
[data-theme="light"] .error-dismiss { color: #dc2626; }
[data-theme="light"] .pagination .page-info { color: #64748b; }

/* ========== 全屏查看 ========== */
.fullscreen-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  background: #000;
  display: flex;
  flex-direction: column;
}
.fullscreen-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: rgba(0,0,0,0.85);
  flex-shrink: 0;
}
.fullscreen-title { color: #e2e8f0; font-size: 16px; font-weight: 600; }
.fullscreen-body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.fullscreen-body img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

/* ========== 删除对话按钮 ========== */
.panel-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.clear-chat-btn {
  font-size: 12px;
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 6px;
  padding: 3px 10px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}
.clear-chat-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.5);
}

.msg-delete-btn {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: none;
  background: rgba(239, 68, 68, 0.85);
  color: #fff;
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5;
}
.message:hover .msg-delete-btn {
  opacity: 1;
}
.msg-delete-btn:hover {
  background: #ef4444;
}

.message-content {
  position: relative;
}

/* ========== 响应式布局 ========== */
@media (max-width: 1024px) {
  .main-content {
    flex-direction: column;
  }
  .monitor-panel {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid #334155;
    max-height: 55vh;
  }
  .chat-panel {
    width: 100%;
    flex: 1;
    min-height: 0;
  }
  .camera-grid {
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  }
}

@media (max-width: 640px) {
  .header {
    padding: 10px 14px;
  }
  .logo h1 {
    font-size: 15px;
  }
  .badge {
    display: none;
  }
  .panel-header {
    flex-direction: column;
    gap: 10px;
    padding: 10px 14px;
  }
  .panel-actions {
    flex-wrap: wrap;
    width: 100%;
  }
  .tabs {
    overflow-x: auto;
    flex-wrap: nowrap;
  }
  .tab-btn {
    padding: 6px 12px;
    font-size: 13px;
    white-space: nowrap;
  }
  .camera-grid {
    grid-template-columns: 1fr;
    gap: 12px;
    padding: 12px;
  }
  .search-bar {
    flex-wrap: wrap;
    gap: 6px;
    padding: 10px 12px;
  }
  .search-input {
    min-width: 0;
  }
  .stats-row {
    flex-wrap: wrap;
  }
  .stat-card {
    min-width: calc(50% - 8px);
  }
  .modal {
    width: 95%;
    max-width: 420px;
    padding: 18px;
  }
}

/* ========== 亮色主题补充样式 ========== */
[data-theme="light"] .header {
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
[data-theme="light"] .camera-card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.08);
}
[data-theme="light"] .logo-icon {
  color: #3b82f6;
}
[data-theme="light"] .btn-icon {
  color: #64748b;
}
[data-theme="light"] .btn-icon:hover {
  background: rgba(0,0,0,0.05);
  color: #1e293b;
}
[data-theme="light"] .btn:active {
  transform: scale(0.97);
}
[data-theme="light"] .status-indicator.online-dot {
  box-shadow: 0 0 4px rgba(22,163,74,0.3);
}
[data-theme="light"] .thumb-placeholder {
  color: #94a3b8;
}
[data-theme="light"] .data-table tbody tr:hover {
  background: rgba(59,130,246,0.05);
}

</style>
