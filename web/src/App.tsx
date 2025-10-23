import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { Layout, Menu, Button, Input, Avatar, Dropdown, Typography, Drawer } from 'antd';
import { 
  DatabaseOutlined, 
  SettingOutlined, 
  LogoutOutlined, 
  SearchOutlined,
  UserOutlined,
  GlobalOutlined,
  AppstoreOutlined,
  ToolOutlined,
  ExperimentOutlined,
  StarOutlined,
  MenuOutlined
} from '@ant-design/icons';
import KnowledgeBaseList from './components/KnowledgeBaseList';
import Login from './components/Login';
import ResponsiveTest from './components/ResponsiveTest';
import { tokenManager, authApi, setGlobalNavigate } from './services/api';
import { useResponsive } from './hooks/useResponsive';

const { Header, Sider, Content } = Layout;
const { Search } = Input;
const { Title, Text } = Typography;

// 认证保护组件
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const isLoggedIn = tokenManager.isLoggedIn();
  
  if (!isLoggedIn) {
    return <Navigate to="/login" replace />;
  }
  
  return <>{children}</>;
};

// 主布局组件
const MainLayout: React.FC = () => {
  const [selectedMenuKey, setSelectedMenuKey] = useState('knowledge-bases');
  const [mobileMenuVisible, setMobileMenuVisible] = useState(false);
  const responsive = useResponsive();

  const handleLogout = async () => {
    await authApi.logout();
    window.location.href = '/login';
  };

  const handleMenuClick = (key: string) => {
    setSelectedMenuKey(key);
    // 移动端选择菜单后关闭抽屉
    if (responsive.isMobile) {
      setMobileMenuVisible(false);
    }
  };

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人资料',
    },
    {
      key: 'settings',
      icon: <SettingOutlined />,
      label: '设置',
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ];

  const sidebarMenuItems = [
    {
      key: 'knowledge-bases',
      icon: <DatabaseOutlined />,
      label: 'Knowledge Bases',
    },
    {
      key: 'rag-pipeline',
      icon: <AppstoreOutlined />,
      label: 'RAG Pipeline',
    },
    {
      key: 'operations',
      icon: <ToolOutlined />,
      label: 'Operations',
    },
    {
      key: 'models-resources',
      icon: <ExperimentOutlined />,
      label: 'Models & Resources',
    },
    {
      key: 'mcp',
      icon: <StarOutlined />,
      label: 'MCP',
    },
    {
      key: 'responsive-test',
      icon: <SettingOutlined />,
      label: '响应式测试',
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh', width: '100%', maxWidth: '100vw' }}>
      {/* 顶部导航栏 */}
      <Header style={{ 
        padding: responsive.isMobile ? '0 12px' : '0 24px', 
        background: '#f8f9fa',
        borderBottom: '1px solid #e9ecef',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        height: '64px',
        zIndex: 1000,
        position: 'sticky',
        top: 0,
        width: '100%',
        maxWidth: '100vw'
      }}>
        <div style={{ 
          display: 'flex',
          alignItems: 'center',
          gap: responsive.isMobile ? '12px' : '24px'
        }}>
          {/* 移动端菜单按钮 */}
          {responsive.isMobile && (
            <Button
              type="text"
              icon={<MenuOutlined />}
              onClick={() => setMobileMenuVisible(true)}
              style={{ 
                color: '#333',
                fontSize: '18px',
                padding: '4px 8px'
              }}
            />
          )}
          
          <Title level={4} style={{ 
            margin: 0, 
            color: '#333',
            fontSize: responsive.isMobile ? '16px' : '18px',
            fontWeight: '600'
          }}>
            RAG Empowerment System
          </Title>
        </div>

        {/* 搜索框 - 桌面端显示 */}
        {!responsive.isMobile && (
          <div style={{ 
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            flex: 1,
            justifyContent: 'center',
            maxWidth: '600px'
          }}>
            <Search
              placeholder="Search queries, KB names..."
              allowClear
              style={{ width: '100%', maxWidth: '400px' }}
              prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
            />
          </div>
        )}

        <div style={{ 
          display: 'flex',
          alignItems: 'center',
          gap: responsive.isMobile ? '8px' : '16px'
        }}>
          {/* 语言切换 - 桌面端显示 */}
          {!responsive.isMobile && (
            <Button 
              type="text" 
              style={{ 
                color: '#666',
                border: '1px solid #d9d9d9',
                borderRadius: '4px'
              }}
              icon={<GlobalOutlined />}
            >
              中文
            </Button>
          )}
          
          <Dropdown
            menu={{ items: userMenuItems }}
            placement="bottomRight"
            arrow
          >
            <Avatar 
              size={responsive.isMobile ? 28 : 32} 
              icon={<UserOutlined />}
              style={{ 
                cursor: 'pointer',
                background: '#e91e63'
              }}
            />
          </Dropdown>
        </div>
      </Header>

      <Layout style={{ width: '100%', maxWidth: '100vw' }}>
        {/* 桌面端侧边栏 */}
        {!responsive.isMobile && (
          <Sider
            width={280}
            style={{
              background: '#f8f9fa',
              position: 'sticky',
              top: '64px',
              height: 'calc(100vh - 64px)',
              overflow: 'auto',
              maxWidth: '280px',
              borderRight: '1px solid #e9ecef'
            }}
          >
            <div style={{ 
              padding: '24px 16px 16px',
              borderBottom: '1px solid #e9ecef',
              background: '#e91e63',
              margin: '0 -1px 0 -1px'
            }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '12px'
              }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  background: '#fff',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '18px',
                  fontWeight: 'bold',
                  color: '#e91e63'
                }}>
                  T
                </div>
                <Title level={4} style={{ 
                  margin: 0, 
                  color: '#fff',
                  fontSize: '16px',
                  fontWeight: '600'
                }}>
                  T-Systems Enterprise
                </Title>
              </div>
            </div>
            
            <Menu
              mode="inline"
              selectedKeys={[selectedMenuKey]}
              items={sidebarMenuItems}
              onClick={({ key }) => handleMenuClick(key)}
              style={{
                background: '#f8f9fa',
                border: 'none',
                marginTop: '16px'
              }}
              theme="light"
            />

            <div style={{ 
              position: 'absolute',
              bottom: '16px',
              left: '16px',
              right: '16px',
              textAlign: 'center'
            }}>
              <Text style={{ color: '#6c757d', fontSize: '12px' }}>
                © 2025 T-Systems
              </Text>
            </div>
          </Sider>
        )}

        {/* 移动端抽屉菜单 */}
        <Drawer
          title="菜单"
          placement="left"
          onClose={() => setMobileMenuVisible(false)}
          open={mobileMenuVisible}
          width={280}
          bodyStyle={{ padding: 0 }}
          headerStyle={{ 
            background: '#e91e63',
            color: '#fff',
            borderBottom: '1px solid #e9ecef'
          }}
        >
          <div style={{ 
            padding: '16px',
            borderBottom: '1px solid #e9ecef',
            textAlign: 'center',
            background: '#f8f9fa'
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '12px'
            }}>
              <div style={{
                width: '28px',
                height: '28px',
                background: '#e91e63',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '16px',
                fontWeight: 'bold',
                color: '#fff'
              }}>
                T
              </div>
              <Title level={4} style={{ 
                margin: 0, 
                color: '#333',
                fontSize: '16px',
                fontWeight: '600'
              }}>
                T-Systems Enterprise
              </Title>
            </div>
          </div>
          
          <Menu
            mode="inline"
            selectedKeys={[selectedMenuKey]}
            items={sidebarMenuItems}
            onClick={({ key }) => handleMenuClick(key)}
            style={{
              background: '#f8f9fa',
              border: 'none',
              marginTop: '16px'
            }}
            theme="light"
          />

          <div style={{ 
            position: 'absolute',
            bottom: '16px',
            left: '16px',
            right: '16px',
            textAlign: 'center'
          }}>
            <Text style={{ color: '#6c757d', fontSize: '12px' }}>
              © 2025 T-Systems
            </Text>
          </div>
        </Drawer>

        {/* 主内容区域 */}
        <Content
          style={{
            background: '#fff',
            padding: responsive.isMobile ? '16px 12px' : '24px',
            minHeight: 'calc(100vh - 64px)',
            overflow: 'auto',
            width: '100%',
            maxWidth: '100vw'
          }}
        >
          {/* 移动端搜索框 */}
          {responsive.isMobile && (
            <div style={{ marginBottom: '16px' }}>
              <Search
                placeholder="Search queries, KB names..."
                allowClear
                style={{ width: '100%' }}
                prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
              />
            </div>
          )}
          
          {selectedMenuKey === 'knowledge-bases' && <KnowledgeBaseList />}
          {selectedMenuKey === 'rag-pipeline' && (
            <div style={{ textAlign: 'center', padding: responsive.isMobile ? '40px 0' : '60px 0' }}>
              <Title level={3} style={{ color: '#666' }}>RAG Pipeline</Title>
              <Text type="secondary">RAG管道功能开发中...</Text>
            </div>
          )}
          {selectedMenuKey === 'operations' && (
            <div style={{ textAlign: 'center', padding: responsive.isMobile ? '40px 0' : '60px 0' }}>
              <Title level={3} style={{ color: '#666' }}>Operations</Title>
              <Text type="secondary">操作管理功能开发中...</Text>
            </div>
          )}
          {selectedMenuKey === 'models-resources' && (
            <div style={{ textAlign: 'center', padding: responsive.isMobile ? '40px 0' : '60px 0' }}>
              <Title level={3} style={{ color: '#666' }}>Models & Resources</Title>
              <Text type="secondary">模型与资源管理功能开发中...</Text>
            </div>
          )}
          {selectedMenuKey === 'mcp' && (
            <div style={{ textAlign: 'center', padding: responsive.isMobile ? '40px 0' : '60px 0' }}>
              <Title level={3} style={{ color: '#666' }}>MCP</Title>
              <Text type="secondary">MCP功能开发中...</Text>
            </div>
          )}
          {selectedMenuKey === 'responsive-test' && <ResponsiveTest />}
        </Content>
      </Layout>
    </Layout>
  );
};

const App: React.FC = () => {
  const navigate = useNavigate();

  // 设置全局导航管理器
  useEffect(() => {
    console.log('Setting global navigate function');
    setGlobalNavigate(navigate);
    console.log('Global navigate function set successfully');
  }, [navigate]);

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route 
        path="/" 
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        } 
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

export default App;