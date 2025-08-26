'use client';

import React, { useState } from 'react';
import { X, AlertTriangle } from 'lucide-react';
import { useAccount, useWalletClient } from 'wagmi';
import { apiService } from '../services/api';

interface TransactionData {
  from?: string;
  to?: string;
  data?: string;
  gas?: string | number;
  gasPrice?: string | number;
  nonce?: number;
  chainId?: number;
  value?: string | number;
  // Additional MCP data
  mcpResponse?: any;
  estimated_gas?: number;
  gas_price_gwei?: number;
  user_address?: string;
}

interface ApprovalRequest {
  approval_id: string;
  transaction_data: TransactionData;
  timestamp: string;
  message: string;
}

interface TransactionModalProps {
  isOpen: boolean;
  onClose: () => void;
  transactionData?: TransactionData | null;
  approvalRequest?: ApprovalRequest | null;
  onConfirm?: () => void;
  onApprovalSubmit?: (approvalId: string, approved: boolean, signedTxHex?: string, rejectionReason?: string) => Promise<boolean>;
  mode?: 'transaction' | 'approval'; // New prop to distinguish modes
}

export const TransactionModal: React.FC<TransactionModalProps> = ({
  isOpen,
  onClose,
  transactionData,
  approvalRequest,
  onConfirm,
  onApprovalSubmit,
  mode = 'transaction',
}) => {
  const { address } = useAccount();
  const { data: walletClient } = useWalletClient();
  const [isConfirming, setIsConfirming] = useState(false);
  const [signStatus, setSignStatus] = useState<'idle' | 'approving' | 'signing' | 'broadcasting' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [rejectionReason] = useState<string>('');

  // Get transaction data from either direct prop or approval request
  const currentTransactionData = transactionData || approvalRequest?.transaction_data;
  
  if (!isOpen || !currentTransactionData) return null;

  const isApprovalMode = mode === 'approval' && approvalRequest;

  const handleConfirm = async () => {
    if (!walletClient || !address) {
      setErrorMessage('Wallet not connected');
      return;
    }

    setIsConfirming(true);
    setErrorMessage('');

    try {
      if (isApprovalMode && onApprovalSubmit) {
        // Approval mode: First approve, then sign and submit
        setSignStatus('approving');
        console.log('Approving deployment request:', approvalRequest?.approval_id);
        
        setSignStatus('signing');
        console.log('Transaction data received:', currentTransactionData);
        
        // Prepare transaction for signing
        const txToSign = {
          from: address as `0x${string}`,
          to: currentTransactionData.to as `0x${string}` | undefined,
          data: currentTransactionData.data as `0x${string}`,
          gas: BigInt(currentTransactionData.gas || currentTransactionData.estimated_gas || 2000000),
          gasPrice: BigInt(currentTransactionData.gasPrice || (currentTransactionData.gas_price_gwei ? Math.floor(currentTransactionData.gas_price_gwei * 1e9) : 10e9)),
          nonce: currentTransactionData.nonce || undefined,
          chainId: currentTransactionData.chainId,
          value: BigInt(currentTransactionData.value || 0),
        };

        console.log('Signing transaction:', txToSign);

        try {
          // Try direct signing first (works with some wallets)
          const signedTransaction = await walletClient.signTransaction(txToSign);
          console.log('Transaction signed:', signedTransaction);

          // Submit approval with signed transaction
          const approvalSuccess = await onApprovalSubmit(
            approvalRequest!.approval_id, 
            true, 
            signedTransaction
          );

          if (approvalSuccess) {
            setSignStatus('success');
            console.log('Approval and signed transaction submitted successfully');
            
            // Close modal after a short delay
            setTimeout(() => {
              onClose();
              setSignStatus('idle');
            }, 2000);
          } else {
            throw new Error('Failed to submit approval response');
          }

        } catch (signError: any) {
          console.log('Direct signing failed, trying sendTransaction approach:', signError);
          
          // Alternative approach: Use sendTransaction and get the hash
          if (signError.message?.includes('eth_signTransaction') || signError.message?.includes('not supported')) {
            setSignStatus('broadcasting');
            
            try {
              // Send the transaction directly and get the hash
              const txHash = await walletClient.sendTransaction(txToSign);
              console.log('Transaction sent, hash:', txHash);

              // Submit approval with transaction hash (the backend will handle broadcasting)
              const approvalSuccess = await onApprovalSubmit(
                approvalRequest!.approval_id, 
                true, 
                txHash // Pass the transaction hash instead of signed data
              );

              if (approvalSuccess) {
                setSignStatus('success');
                console.log('Approval and transaction submitted successfully');
                
                // Close modal after a short delay
                setTimeout(() => {
                  onClose();
                  setSignStatus('idle');
                }, 2000);
              } else {
                throw new Error('Failed to submit approval response');
              }

            } catch (sendError) {
              console.error('SendTransaction also failed:', sendError);
              throw new Error('Unable to sign or send transaction. Please try again.');
            }
          } else {
            throw signError;
          }
        }

      } else {
        // Direct transaction mode (legacy)
        setSignStatus('signing');
        console.log('Transaction data received:', currentTransactionData);
        
        // Prepare transaction for signing
        const txToSign = {
          from: address as `0x${string}`,
          to: currentTransactionData.to as `0x${string}` | undefined,
          data: currentTransactionData.data as `0x${string}`,
          gas: BigInt(currentTransactionData.gas || currentTransactionData.estimated_gas || 2000000),
          gasPrice: BigInt(currentTransactionData.gasPrice || (currentTransactionData.gas_price_gwei ? Math.floor(currentTransactionData.gas_price_gwei * 1e9) : 10e9)),
          nonce: currentTransactionData.nonce || undefined,
          chainId: currentTransactionData.chainId,
          value: BigInt(currentTransactionData.value || 0),
        };

        console.log('Signing transaction:', txToSign);

        // Sign the transaction with MetaMask
        const signedTransaction = await walletClient.signTransaction(txToSign);
        console.log('Transaction signed:', signedTransaction);

        setSignStatus('broadcasting');

        // Send signed transaction to backend for broadcasting
        const broadcastResponse = await apiService.broadcastSignedTransaction(signedTransaction);
        
        if (broadcastResponse.success) {
          setSignStatus('success');
          console.log('Transaction broadcast successful:', broadcastResponse);
          
          // Call the original onConfirm callback if provided
          if (onConfirm) {
            onConfirm();
          }
          
          // Close modal after a short delay
          setTimeout(() => {
            onClose();
            setSignStatus('idle');
          }, 2000);
        } else {
          throw new Error(broadcastResponse.error || 'Failed to broadcast transaction');
        }
      }

    } catch (error: any) {
      console.error('Transaction signing/broadcasting failed:', error);
      setSignStatus('error');
      setErrorMessage(error.message || 'Transaction failed');
    } finally {
      setIsConfirming(false);
    }
  };

  const handleReject = async () => {
    // Reset confirmation state immediately to allow cancellation
    setIsConfirming(false);
    setSignStatus('idle');
    setErrorMessage('');
    
    if (isApprovalMode && onApprovalSubmit && approvalRequest) {
      setIsConfirming(true);
      setSignStatus('approving');
      
      try {
        const success = await onApprovalSubmit(
          approvalRequest.approval_id,
          false,
          undefined,
          rejectionReason || 'User rejected deployment'
        );

        if (success) {
          console.log('Deployment rejected successfully');
          onClose();
        } else {
          throw new Error('Failed to submit rejection');
        }
      } catch (error: any) {
        console.error('Error rejecting deployment:', error);
        setErrorMessage(error.message || 'Failed to reject deployment');
        setSignStatus('error');
      } finally {
        setIsConfirming(false);
      }
    } else {
      // Just close for non-approval mode
      onClose();
    }
  };

  const formatGwei = (wei: string | number | undefined) => {
    if (!wei) return 'N/A';
    try {
      return (Number(wei) / 1e9).toFixed(2) + ' Gwei';
    } catch {
      return 'N/A';
    }
  };

  const formatEther = (wei: string | number | undefined) => {
    if (!wei) return '0';
    try {
      return (Number(wei) / 1e18).toFixed(6) + ' ETH';
    } catch {
      return '0 ETH';
    }
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content transaction-modal">
        <div className="modal-header">
          <h3>Confirm Contract Deployment</h3>
          <button onClick={() => {
            // Reset state when closing via X button
            setIsConfirming(false);
            setSignStatus('idle');
            setErrorMessage('');
            onClose();
          }} className="modal-close">
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          <div className="transaction-warning">
            <AlertTriangle size={20} className="warning-icon" />
            <p>
              You are about to deploy a smart contract. Please review the transaction details carefully.
            </p>
          </div>

          <div className="transaction-details">
            <div className="detail-row">
              <span className="detail-label">From:</span>
              <span className="detail-value">
                {address ? `${address.slice(0, 6)}...${address.slice(-4)}` : 'N/A'}
              </span>
            </div>

            <div className="detail-row">
              <span className="detail-label">Type:</span>
              <span className="detail-value">Contract Deployment</span>
            </div>

            <div className="detail-row">
              <span className="detail-label">Gas Limit:</span>
              <span className="detail-value">
                {currentTransactionData.gas ? Number(currentTransactionData.gas).toLocaleString() : 'N/A'}
              </span>
            </div>

            <div className="detail-row">
              <span className="detail-label">Gas Price:</span>
              <span className="detail-value">{formatGwei(currentTransactionData.gasPrice)}</span>
            </div>

            <div className="detail-row">
              <span className="detail-label">Estimated Fee:</span>
              <span className="detail-value">
                {currentTransactionData.gas && currentTransactionData.gasPrice
                  ? formatEther((BigInt(Number(currentTransactionData.gas)) * BigInt(Number(currentTransactionData.gasPrice))).toString())
                  : 'N/A'}
              </span>
            </div>

            <div className="detail-row">
              <span className="detail-label">Network:</span>
              <span className="detail-value">
                {currentTransactionData.chainId === 11155111 ? 'Sepolia Testnet' : `Chain ID: ${currentTransactionData.chainId}`}
              </span>
            </div>
          </div>

        </div>

        {/* Status Messages */}
        {signStatus !== 'idle' && (
          <div className={`status-message ${signStatus}`}>
            {signStatus === 'approving' && '🔄 Submitting approval response...'}
            {signStatus === 'signing' && '🔄 Please sign the transaction in your wallet...'}
            {signStatus === 'broadcasting' && '📡 Broadcasting transaction to network...'}
            {signStatus === 'success' && '✅ Transaction successful! Contract deployed.'}
            {signStatus === 'error' && `❌ ${errorMessage}`}
          </div>
        )}

        <div className="modal-footer">
          <button 
            onClick={handleReject} 
            className="btn-secondary" 
            disabled={signStatus === 'success'}
          >
            {signStatus === 'success' ? 'Close' : (isApprovalMode ? 'Reject' : 'Cancel')}
          </button>
          <button 
            onClick={handleConfirm} 
            className="btn-primary" 
            disabled={isConfirming || !address || signStatus === 'success'}
          >
            {isConfirming ? (
              signStatus === 'approving' ? 'Processing...' :
              signStatus === 'signing' ? 'Signing...' :
              signStatus === 'broadcasting' ? 'Broadcasting...' : 'Processing...'
            ) : (isApprovalMode ? 'Approve & Sign' : 'Sign & Deploy')}
          </button>
        </div>
      </div>
    </div>
  );
};