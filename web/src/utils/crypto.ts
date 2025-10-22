/**
 * 密码加密工具
 * 使用与原始RagFlow完全一致的RSA加密算法
 * 基于JSEncrypt库和Base64编码
 */

import JSEncrypt from 'jsencrypt';
import { Base64 } from 'js-base64';

/**
 * 原始RagFlow的RSA公钥
 * 与ragflow-web/ragflow/web/src/utils/index.ts中的公钥完全一致
 */
const RSA_PUBLIC_KEY = `-----BEGIN PUBLIC KEY-----MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEArq9XTUSeYr2+N1h3Afl/z8Dse/2yD0ZGrKwx+EEEcdsBLca9Ynmx3nIB5obmLlSfmskLpBo0UACBmB5rEjBp2Q2f3AG3Hjd4B+gNCG6BDaawuDlgANIhGnaTLrIqWrrcm4EMzJOnAOI1fgzJRsOOUEfaS318Eq9OVO3apEyCCt0lOQK6PuksduOjVxtltDav+guVAA068NrPYmRNabVKRNLJpL8w4D44sfth5RvZ3q9t+6RTArpEtc5sh5ChzvqPOzKGMXW83C95TxmXqpbK6olN4RevSfVjEAgCydH6HN6OhtOQEcnrU97r9H0iZOWwbw3pVrZiUkuRD1R56Wzs2wIDAQAB-----END PUBLIC KEY-----`;

/**
 * 使用原始RagFlow的加密算法加密密码
 * 实现方式：Base64编码 + RSA加密
 * @param password 原始密码
 * @returns string 加密后的密码
 */
export function encryptPassword(password: string): string {
  try {
    // 创建JSEncrypt实例
    const encryptor = new JSEncrypt();
    
    // 设置公钥
    encryptor.setPublicKey(RSA_PUBLIC_KEY);
    
    // 先进行Base64编码，再进行RSA加密
    const base64Password = Base64.encode(password);
    const encryptedPassword = encryptor.encrypt(base64Password);
    
    if (!encryptedPassword) {
      throw new Error('RSA加密失败');
    }
    
    return encryptedPassword;
  } catch (error) {
    console.error('密码加密失败:', error);
    throw new Error('密码加密失败');
  }
}

/**
 * 兼容性函数 - 保持与之前API的一致性
 * @param password 原始密码
 * @returns Promise<string> 加密后的密码
 */
export async function encryptPasswordAsync(password: string): Promise<string> {
  return encryptPassword(password);
}

/**
 * 检查加密功能是否可用
 * @returns boolean 是否支持加密
 */
export function isCryptoSupported(): boolean {
  try {
    // 测试加密功能
    const testPassword = 'test123';
    const encrypted = encryptPassword(testPassword);
    return !!encrypted;
  } catch (error) {
    console.warn('加密功能不可用:', error);
    return false;
  }
}
