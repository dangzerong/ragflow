import React, { useState } from 'react';
import { Form, Input, Button, Card, message, Typography, Tabs, Checkbox } from 'antd';
import { UserOutlined, LockOutlined, GlobalOutlined } from '@ant-design/icons';
import { authApi, tokenManager } from '../services/api';
import { encryptPassword, isCryptoSupported } from '../utils/crypto';
import { useResponsive } from '../hooks/useResponsive';
import type { LoginRequest } from '../types/api';

const { Title, Text } = Typography;
const { TabPane } = Tabs;

const Login: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();
  const responsive = useResponsive();

  const handleLogin = async (values: LoginRequest) => {
    setLoading(true);
    try {
      // 检查是否支持加密
      if (!isCryptoSupported()) {
        message.error('浏览器不支持密码加密，请使用现代浏览器');
        return;
      }

      // 加密密码 - 使用原始RagFlow的加密算法
      const encryptedPassword = encryptPassword(values.password);
      
      // 使用加密后的密码发送登录请求
      const loginData: LoginRequest = {
        email: values.email,
        password: encryptedPassword
      };

      const response = await authApi.login(loginData);
      console.log('Login response:', response);
      message.success("code: " + response.code);
      if (response.code === 0) {
        // 从响应头获取token
        const token = response.headers?.authorization || response.headers?.Authorization;
        console.log('Token from headers:', token);
        if (token) {
          // 保存token
          tokenManager.setToken(token);
          console.log('Token saved to localStorage');
          message.success('登录成功');
          
          // 跳转到主页
          window.location.href = '/';
        } else {
          message.error('登录响应中未找到token');
        }
      } else {
        message.error(response.message || '登录失败');
      }
    } catch (error: any) {
      console.error('Login error:', error);
      message.error(error.response?.data?.message || '登录失败，请检查网络连接');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: '#f8f9fa',
      position: 'relative'
    }}>
      {/* 自定义样式 */}
      <style>{`
        .login-tabs .ant-tabs-tab.ant-tabs-tab-active .ant-tabs-tab-btn {
          color: #e91e63 !important;
        }
        .login-tabs .ant-tabs-ink-bar {
          background: #e91e63 !important;
        }
        .login-tabs .ant-tabs-tab {
          color: #666 !important;
          font-weight: 500;
        }
        .login-tabs .ant-tabs-tab:hover {
          color: #e91e63 !important;
        }
        .login-card {
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08) !important;
          border-radius: 12px !important;
        }
        .login-input .ant-input {
          border-radius: 8px !important;
          border: 1px solid #e9ecef !important;
        }
        .login-input .ant-input:focus {
          border-color: #e91e63 !important;
          box-shadow: 0 0 0 2px rgba(233, 30, 99, 0.1) !important;
        }
        .login-button {
          border-radius: 8px !important;
          height: 48px !important;
          font-weight: 500 !important;
        }
      `}</style>

      {/* 顶部横幅 */}
      <div style={{
        height: responsive.isMobile ? '50px' : '60px',
        background: '#e91e63',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: responsive.isMobile ? '0 16px' : '0 24px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <div style={{
            width: responsive.isMobile ? '28px' : '32px',
            height: responsive.isMobile ? '28px' : '32px',
            background: '#fff',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: responsive.isMobile ? '16px' : '18px',
            fontWeight: 'bold',
            color: '#e91e63'
          }}>
            T
          </div>
        </div>
        {!responsive.isMobile && (
          <Button 
            type="text" 
            style={{ 
              color: '#fff',
              border: '1px solid rgba(255,255,255,0.3)',
              borderRadius: '4px'
            }}
            icon={<GlobalOutlined />}
          >
            中文
          </Button>
        )}
      </div>

      {/* 主内容区域 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: responsive.isMobile ? 'calc(100vh - 50px)' : 'calc(100vh - 60px)',
        padding: responsive.isMobile ? '20px 16px' : '40px 20px'
      }}>
        <Card
          className="login-card"
          style={{
            width: '100%',
            maxWidth: responsive.isMobile ? '100%' : 480,
            border: 'none'
          }}
          bodyStyle={{ padding: responsive.isMobile ? '24px' : '32px' }}
        >
          {/* 系统标题 */}
          <div style={{ textAlign: 'center', marginBottom: responsive.isMobile ? '16px' : '20px' }}>
            <Title level={2} style={{ 
              marginBottom: '4px', 
              color: '#1a1a1a',
              fontSize: responsive.isMobile ? '16px' : '20px',
              fontWeight: '600'
            }}>
              {responsive.isMobile ? 'RAG Empowerment System' : 'T-Systems Enterprise RAG Empowerment System'}
            </Title>
          </div>

          {/* 登录/注册标签 */}
          <Tabs 
            className="login-tabs"
            defaultActiveKey="login" 
            centered
            style={{ marginBottom: '20px' }}
            tabBarStyle={{ 
              borderBottom: '2px solid #f0f0f0',
              marginBottom: '16px'
            }}
          >
            <TabPane tab="登录" key="login" />
            <TabPane tab="注册" key="register" />
          </Tabs>

          {/* 欢迎语 */}
          <div style={{ textAlign: 'center', marginBottom: responsive.isMobile ? '16px' : '20px' }}>
            <Title level={3} style={{ 
              marginBottom: '4px', 
              color: '#1a1a1a',
              fontSize: responsive.isMobile ? '14px' : '16px',
              fontWeight: '500'
            }}>
              很高兴再次见到您!
            </Title>
          </div>

          {/* 登录表单 */}
          <Form
            form={form}
            name="login"
            onFinish={handleLogin}
            layout="vertical"
            size="large"
          >
            <Form.Item
              name="email"
              rules={[
                { required: true, message: '请输入邮箱地址' },
                { type: 'email', message: '请输入有效的邮箱地址' }
              ]}
              className="login-input"
            >
              <Input
                prefix={<UserOutlined style={{ color: '#999' }} />}
                placeholder="请输入邮箱地址"
                autoComplete="email"
                style={{
                  height: responsive.isMobile ? '36px' : '40px',
                  fontSize: responsive.isMobile ? '12px' : '14px'
                }}
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[
                { required: true, message: '请输入密码' },
                { min: 6, message: '密码至少6位' }
              ]}
              className="login-input"
            >
              <Input.Password
                prefix={<LockOutlined style={{ color: '#999' }} />}
                placeholder="请输入密码"
                autoComplete="current-password"
                style={{
                  height: responsive.isMobile ? '36px' : '40px',
                  fontSize: responsive.isMobile ? '12px' : '14px'
                }}
              />
            </Form.Item>

            <Form.Item style={{ marginBottom: '16px' }}>
              <Checkbox style={{ color: '#1a1a1a', fontSize: '12px' }}>
                记住我
              </Checkbox>
            </Form.Item>

            <Form.Item style={{ marginBottom: 0 }}>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                className="login-button"
                style={{
                  fontSize: responsive.isMobile ? '12px' : '14px',
                  height: responsive.isMobile ? '36px' : '40px',
                  background: '#e91e63',
                  borderColor: '#e91e63'
                }}
              >
                {loading ? '登录中...' : '登录'}
              </Button>
            </Form.Item>
          </Form>

          {/* 注册链接 */}
          <div style={{ textAlign: 'center', marginTop: '16px' }}>
            <Text style={{ color: '#1a1a1a', fontSize: '12px' }}>
              没有帐户? 
              <Button 
                type="link" 
                style={{ 
                  color: '#e91e63',
                  padding: '0 4px',
                  height: 'auto',
                  fontSize: '12px'
                }}
              >
                注册
              </Button>
            </Text>
          </div>
        </Card>
      </div>

      {/* 底部版权信息 */}
      <div style={{
        position: 'absolute',
        bottom: '0',
        left: '0',
        right: '0',
        height: responsive.isMobile ? '50px' : '60px',
        background: '#fff',
        borderTop: '1px solid #f0f0f0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: responsive.isMobile ? '0 16px' : '0 24px',
        flexDirection: responsive.isMobile ? 'column' : 'row',
        gap: responsive.isMobile ? '4px' : '0'
      }}>
        <Text style={{ color: '#999', fontSize: responsive.isMobile ? '10px' : '12px' }}>
          © Deutsche Telekom AG
        </Text>
        {!responsive.isMobile && (
          <div style={{ display: 'flex', gap: '16px' }}>
            <Button type="link" style={{ color: '#999', fontSize: '12px', padding: '0' }}>
              Imprint
            </Button>
            <Button type="link" style={{ color: '#999', fontSize: '12px', padding: '0' }}>
              Data privacy
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default Login;