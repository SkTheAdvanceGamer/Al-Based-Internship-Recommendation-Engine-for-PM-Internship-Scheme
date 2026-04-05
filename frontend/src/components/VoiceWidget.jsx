import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Mic, MicOff, X, Volume2 } from 'lucide-react';

/**
 * VoiceWidget — Floating Action Button for OmniDimension Voice AI
 *
 * This component provides a highly visible, mobile-friendly "Tap to Speak"
 * button. OmniDimension's embed script handles the actual voice capture —
 * this component provides a branded UI container and visual cues.
 *
 * The OmniDimension widget will be loaded via index.html <script> tag.
 * This FAB serves as a visual touchpoint that can optionally trigger
 * the OmniDimension widget or display status.
 */
export function VoiceWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [pulse, setPulse] = useState(true);

  return (
    <>
      {/* Floating Action Button */}
      <motion.button
        id="voice-widget-fab"
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 left-6 z-[60] w-16 h-16 md:w-[72px] md:h-[72px] rounded-full
          bg-gradient-to-br from-orange-500 via-orange-600 to-red-600
          text-white shadow-[0_0_30px_rgba(255,100,0,0.5)] border-2 border-orange-400/50
          flex items-center justify-center cursor-pointer
          hover:scale-110 active:scale-95 transition-transform"
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 400, damping: 15, delay: 1 }}
        aria-label="Tap to speak your requirements"
      >
        {isOpen ? <X size={28} /> : <Mic size={28} />}

        {/* Pulsing ring animation — attention grabber */}
        {!isOpen && pulse && (
          <>
            <span className="absolute inset-0 rounded-full animate-ping bg-orange-500/30" />
            <span className="absolute -inset-1 rounded-full animate-pulse border-2 border-orange-400/40" />
          </>
        )}
      </motion.button>

      {/* "Tap to Speak" label — shown on first load */}
      <AnimatePresence>
        {!isOpen && (
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ delay: 1.5 }}
            className="fixed bottom-[26px] left-[90px] md:left-[100px] z-[60] pointer-events-none"
          >
            <div className="bg-black/90 border border-orange-500/40 px-4 py-2 rounded-lg
              shadow-[0_0_20px_rgba(255,100,0,0.2)] backdrop-blur-sm">
              <p className="text-orange-400 font-bold text-xs md:text-sm tracking-wider uppercase whitespace-nowrap">
                🎙️ Tap to Speak
              </p>
              <p className="text-white/60 text-[10px] tracking-wide">
                Tell us your skills & location
              </p>
            </div>
            {/* Arrow pointing to FAB */}
            <div className="absolute top-1/2 -left-2 -translate-y-1/2 w-0 h-0
              border-t-[6px] border-t-transparent
              border-r-[8px] border-r-black/90
              border-b-[6px] border-b-transparent" />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Expanded Voice Panel */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            id="voice-widget-panel"
            initial={{ opacity: 0, y: 50, scale: 0.8 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 50, scale: 0.8 }}
            transition={{ type: 'spring', stiffness: 300, damping: 25 }}
            className="fixed bottom-24 left-4 right-4 md:left-6 md:right-auto md:w-[380px] z-[60]
              bg-gradient-to-b from-gray-900 to-black border border-orange-500/30
              rounded-2xl shadow-[0_0_40px_rgba(255,100,0,0.15)] overflow-hidden"
          >
            {/* Header */}
            <div className="bg-gradient-to-r from-orange-600 to-red-600 px-5 py-4 flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center backdrop-blur-sm">
                <Volume2 size={20} className="text-white" />
              </div>
              <div>
                <h3 className="text-white font-bold text-sm tracking-wider uppercase">
                  Voice Assistant
                </h3>
                <p className="text-white/70 text-[11px]">PM Internship Scheme</p>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="ml-auto text-white/60 hover:text-white transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Body — OmniDimension container */}
            <div className="p-5">
              <div className="text-center mb-4">
                <p className="text-white/80 text-sm leading-relaxed">
                  Speak your requirements in <strong className="text-orange-400">Hindi</strong>,{' '}
                  <strong className="text-orange-400">English</strong>, or{' '}
                  <strong className="text-orange-400">Telugu</strong>
                </p>
                <p className="text-white/50 text-xs mt-1">
                  "मुझे Delhi में IT internship चाहिए"
                </p>
              </div>

              {/* ================================================ */}
              {/* OMNIDIMENSION WIDGET CONTAINER                    */}
              {/* If OmniDimension renders an inline widget,        */}
              {/* target this container with its SDK.               */}
              {/* ================================================ */}
              <div
                id="omnidimension-voice-container"
                className="min-h-[120px] rounded-xl bg-white/5 border border-white/10
                  flex items-center justify-center p-4"
              >
                {/* Placeholder UI — will be replaced by OmniDimension widget */}
                <div className="text-center">
                  <div className="w-16 h-16 mx-auto rounded-full bg-orange-500/20 border-2 border-orange-500/40
                    flex items-center justify-center mb-3 animate-pulse">
                    <Mic size={28} className="text-orange-400" />
                  </div>
                  <p className="text-white/40 text-xs tracking-wider uppercase">
                    Voice widget loading...
                  </p>
                  <p className="text-white/30 text-[10px] mt-1">
                    Powered by OmniDimension
                  </p>
                </div>
              </div>

              {/* Instructions */}
              <div className="mt-4 space-y-2">
                <div className="flex items-start gap-2 text-white/50 text-[11px]">
                  <span className="text-orange-400 font-bold">1.</span>
                  <span>Tell us your <strong className="text-white/70">skills</strong> (e.g., "Excel, data entry, typing")</span>
                </div>
                <div className="flex items-start gap-2 text-white/50 text-[11px]">
                  <span className="text-orange-400 font-bold">2.</span>
                  <span>Mention your <strong className="text-white/70">location</strong> & preferred <strong className="text-white/70">sector</strong></span>
                </div>
                <div className="flex items-start gap-2 text-white/50 text-[11px]">
                  <span className="text-orange-400 font-bold">3.</span>
                  <span>We'll recommend the <strong className="text-white/70">top 5 PM Scheme internships</strong> for you!</span>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="px-5 py-3 bg-white/5 border-t border-white/10 flex items-center justify-between">
              <span className="text-white/30 text-[10px] tracking-wider">
                BACKEND: POST /api/voice-recommend
              </span>
              <span className="text-orange-400/60 text-[10px] tracking-wider font-bold">
                OMNIDIMENSION AI
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
