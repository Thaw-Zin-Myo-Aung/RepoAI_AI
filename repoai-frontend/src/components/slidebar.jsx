import { Coffee, Plus, Menu, User } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';

export default function SidebarLayout({ children }) {
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (path) => location.pathname === path;

  return (
    <div className="min-h-screen flex text-white bg-[#343A40]">
      
      {/* Sidebar */}
      <aside className="border-none min-w-[22%] pr-2 bg-[#212121] flex flex-col">
        <div 
          className=" border-none justify-start pl-10 flex items-center cursor-pointer h-[18%]"
          onClick={() => navigate('/home')}
        >
          <div className="w-12 h-12 flex items-center justify-center">
            <Coffee className="w-8 h-8 text-[#FFFFFF] " />
          </div>
          <span className="text-xl font-[900] text-[#FFFFFF]">Repo AI</span>
        </div>

        <nav className="space-y-2 flex flex-col h-[40%] justify-evenly">
          <button
            onClick={() => navigate('/init-chat')}
            className={`
              pl-10 border-none w-full justify-start flex items-center gap-4 py-[20px] rounded-xl transition-colors 
              bg-[#212121]
              ${isActive('/init-chat') || isActive('/home') ? 'bg-[#121212]' : 'hover:bg-[#343A40]'}
            `}
          >
            <div className={`
              w-10 h-10 p-[5px] flex items-center justify-center rounded-lg gap
              bg-[#404040] mr-[10px]
              ${isActive('/init-chat') || isActive('/home') ? 'bg-[#404040]' : 'hover:bg-[#343A40]'}
            `}>
              <Plus className="w-5 h-5 text-[#FFFFFF]" />
            </div>
            <span className="font-medium text-[#FFFFFF]">New Chat</span>
          </button>

          <button
            onClick={() => navigate('/chat-history')}
            className={`
              pl-10 border-none w-full justify-start flex items-center gap-4 py-[20px]  rounded-xl transition-colors 
              bg-[#212121]
              ${isActive('/chat') ? 'bg-[#121212]' : 'hover:bg-[#343A40]'}
            `}
          >
            <div className={`
              w-10 h-10 p-[5px] flex items-center justify-center rounded-lg
              bg-[#404040] mr-[10px]
              ${isActive('/chat') ? 'bg-[#404040]' : 'hover:bg-[#343A40]'}
            `}>
              <Menu className="w-5 h-5 text-[#FFFFFF]" />
            </div>
            <span className="font-medium text-[#FFFFFF]">Chat History</span>
          </button>

          <button
            onClick={() => navigate('/profile')}
            className={`
              pl-10 border-none w-full justify-start flex items-center gap-4 py-[20px] rounded-xl transition-colors 
              bg-[#212121] 
              ${isActive('/profile') ? 'bg-[#121212]' : 'hover:bg-[#343A40]'}
            `}
          >
            <div className={`
              w-10 h-10 p-[5px] flex items-center justify-center rounded-lg
              bg-[#404040] mr-[10px]
              ${isActive('/profile') ? 'bg-[#121212]' : 'hover:bg-[#343A40]'}
            `}>
              <User className="w-5 h-5 text-[#FFFFFF]" />
            </div>
            <span className="font-medium text-[#FFFFFF]">Profile</span>
          </button>
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1">
        {children} 
      </main>
    </div>
  );
}
