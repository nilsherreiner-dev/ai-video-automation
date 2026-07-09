import React, { useState, useEffect } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Play, Pause, Settings, Share2, TrendingUp, Eye, Heart, MessageCircle } from 'lucide-react';

const Dashboard = () => {
  const [videos, setVideos] = useState([]);
  const [stats, setStats] = useState({
    totalViews: 0,
    avgCTR: 0,
    avgRetention: 0,
    subscribers: 0
  });
  const [isAutomationRunning, setIsAutomationRunning] = useState(true);
  const [selectedPeriod, setSelectedPeriod] = useState('7d');
  const [trendData, setTrendData] = useState([]);

  // Simulate fetching data from GitHub/API
  useEffect(() => {
    fetchVideoMetrics();
    fetchPerformanceData();
  }, [selectedPeriod]);

  const fetchVideoMetrics = async () => {
    try {
      // In production: fetch from your metrics API
      const mockVideos = [
        {
          id: 1,
          title: "Your Brain is TRICKING You",
          uploadDate: new Date(Date.now() - 86400000).toLocaleDateString(),
          views: 12400,
          ctr: 14.2,
          retention: 68,
          shares: 342,
          comments: 89,
          status: 'published',
          thumbnail: '🧠'
        },
        {
          id: 2,
          title: "OpenAI Just Changed The Game",
          uploadDate: new Date(Date.now() - 172800000).toLocaleDateString(),
          views: 8900,
          ctr: 11.5,
          retention: 62,
          shares: 234,
          comments: 56,
          status: 'published',
          thumbnail: '🤖'
        },
        {
          id: 3,
          title: "Scientist Found IMPOSSIBLE in Arctic",
          uploadDate: new Date(Date.now() - 259200000).toLocaleDateString(),
          views: 15600,
          ctr: 16.8,
          retention: 71,
          shares: 512,
          comments: 145,
          status: 'published',
          thumbnail: '❄️'
        }
      ];
      
      setVideos(mockVideos);
      
      // Calculate aggregate stats
      const totalViews = mockVideos.reduce((sum, v) => sum + v.views, 0);
      const avgCTR = (mockVideos.reduce((sum, v) => sum + v.ctr, 0) / mockVideos.length).toFixed(1);
      const avgRetention = (mockVideos.reduce((sum, v) => sum + v.retention, 0) / mockVideos.length).toFixed(0);
      
      setStats({
        totalViews,
        avgCTR,
        avgRetention,
        subscribers: 1240
      });
    } catch (error) {
      console.error('Error fetching metrics:', error);
    }
  };

  const fetchPerformanceData = () => {
    const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    const mockData = days.map((day, idx) => ({
      name: day,
      views: Math.floor(Math.random() * 15000) + 5000,
      engagement: Math.floor(Math.random() * 15) + 8
    }));
    setTrendData(mockData);
  };

  const toggleAutomation = () => {
    setIsAutomationRunning(!isAutomationRunning);
    // In production: call API to pause/resume
  };

  const StatCard = ({ label, value, icon: Icon, trend }) => (
    <div className="bg-white rounded-lg shadow p-6 flex-1 min-w-[200px]">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-600 text-sm font-medium">{label}</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">{value}</p>
          {trend && (
            <p className="text-green-600 text-sm mt-1">↑ {trend}% from last week</p>
          )}
        </div>
        <Icon className="w-12 h-12 text-blue-500 opacity-20" />
      </div>
    </div>
  );

  const VideoCard = ({ video }) => (
    <div className="bg-white rounded-lg shadow overflow-hidden hover:shadow-lg transition">
      <div className="bg-gradient-to-r from-blue-500 to-purple-600 p-4 text-white flex items-center justify-center text-4xl">
        {video.thumbnail}
      </div>
      
      <div className="p-4">
        <h3 className="font-bold text-gray-900 line-clamp-2">{video.title}</h3>
        <p className="text-xs text-gray-500 mt-1">Posted: {video.uploadDate}</p>
        
        <div className="grid grid-cols-2 gap-3 mt-4">
          <div className="flex items-center gap-2">
            <Eye className="w-4 h-4 text-gray-500" />
            <div>
              <p className="text-xs text-gray-500">Views</p>
              <p className="font-bold text-gray-900">{video.views.toLocaleString()}</p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-gray-500" />
            <div>
              <p className="text-xs text-gray-500">CTR</p>
              <p className="font-bold text-gray-900">{video.ctr}%</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
          <div className="bg-gray-100 rounded p-2">
            <p className="text-gray-600">Retention</p>
            <p className="font-bold text-gray-900">{video.retention}%</p>
          </div>
          <div className="bg-gray-100 rounded p-2">
            <p className="text-gray-600">Engagement</p>
            <p className="font-bold text-gray-900">{video.shares + video.comments}</p>
          </div>
        </div>

        <div className="flex gap-2 mt-4">
          <button className="flex-1 bg-blue-500 text-white py-2 rounded text-sm font-medium hover:bg-blue-600">
            View
          </button>
          <button className="flex-1 bg-gray-100 text-gray-700 py-2 rounded text-sm font-medium hover:bg-gray-200">
            Share
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">📊 Video Dashboard</h1>
              <p className="text-gray-600 text-sm mt-1">AI-Powered Video Automation</p>
            </div>
            
            <div className="flex items-center gap-3">
              <button
                onClick={toggleAutomation}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition ${
                  isAutomationRunning
                    ? 'bg-green-100 text-green-700 hover:bg-green-200'
                    : 'bg-red-100 text-red-700 hover:bg-red-200'
                }`}
              >
                {isAutomationRunning ? (
                  <>
                    <Play className="w-4 h-4" />
                    Automation ON
                  </>
                ) : (
                  <>
                    <Pause className="w-4 h-4" />
                    Automation OFF
                  </>
                )}
              </button>
              
              <button className="bg-gray-100 text-gray-700 p-2 rounded-lg hover:bg-gray-200">
                <Settings className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Section */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard label="Total Views" value={stats.totalViews.toLocaleString()} icon={Eye} trend={12} />
          <StatCard label="Avg CTR" value={`${stats.avgCTR}%`} icon={TrendingUp} trend={8} />
          <StatCard label="Avg Retention" value={`${stats.avgRetention}%`} icon={Heart} trend={5} />
          <StatCard label="Subscribers" value={stats.subscribers.toLocaleString()} icon={MessageCircle} trend={15} />
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Views Trend */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Views Trend</h2>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="views" stroke="#3b82f6" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Engagement */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Engagement Rate</h2>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="engagement" fill="#8b5cf6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Videos Grid */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-900">Recent Videos</h2>
            <select
              value={selectedPeriod}
              onChange={(e) => setSelectedPeriod(e.target.value)}
              className="bg-white border border-gray-300 rounded px-3 py-2 text-sm font-medium text-gray-700"
            >
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
              <option value="90d">Last 90 days</option>
            </select>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {videos.map(video => (
              <VideoCard key={video.id} video={video} />
            ))}
          </div>
        </div>

        {/* Upcoming Videos */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4">📅 Scheduled Videos</h2>
          <div className="space-y-3">
            <div className="border-l-4 border-blue-500 pl-4 py-2">
              <p className="font-medium text-gray-900">Video #4: Google's $100B Mistake</p>
              <p className="text-sm text-gray-600">Scheduled: Tomorrow at 2:00 PM</p>
            </div>
            <div className="border-l-4 border-purple-500 pl-4 py-2">
              <p className="font-medium text-gray-900">Video #5: Scientists Found IMPOSSIBLE</p>
              <p className="text-sm text-gray-600">Scheduled: In 2 days at 9:00 AM</p>
            </div>
            <div className="border-l-4 border-pink-500 pl-4 py-2">
              <p className="font-medium text-gray-900">Video #6: Elon's Hidden Announcement</p>
              <p className="text-sm text-gray-600">Scheduled: In 3 days at 3:00 PM</p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Dashboard;
