import React, { createContext, useState, useContext } from 'react';

const ChatContext = createContext();

export function ChatProvider({ children }) {
  const [chatSessions, setChatSessions] = useState([
    { id: 1, repository: 'Project Alpha', date: '2024-01-15', summary: 'View Details' },
    { id: 2, repository: 'Project Beta', date: '2024-02-20', summary: 'View Details' },
    { id: 3, repository: 'Project Gamma', date: '2024-03-25', summary: 'View Details' },
    { id: 4, repository: 'Project Delta', date: '2024-04-30', summary: 'View Details' },
    { id: 5, repository: 'Project Epsilon', date: '2024-05-05', summary: 'View Details' }
  ]);

  const clearChatHistory = () => setChatSessions([]);

  return (
    <ChatContext.Provider value={{ chatSessions, clearChatHistory }}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  return useContext(ChatContext);
}
// Example component using the ChatContext