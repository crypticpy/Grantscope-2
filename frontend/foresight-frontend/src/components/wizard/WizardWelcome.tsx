import React from "react";
import { Search, Lightbulb, FileEdit } from "lucide-react";

interface WizardWelcomeProps {
  onSelectPath: (path: "have_grant" | "find_grant" | "build_program") => void;
}

interface PathCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
}

const PathCard: React.FC<PathCardProps> = ({
  icon,
  title,
  description,
  onClick,
}) => {
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      className="group flex flex-col items-center text-center p-6 bg-white dark:bg-dark-surface rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm cursor-pointer transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-brand-blue/50 dark:hover:border-brand-blue/50 focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2 dark:focus:ring-offset-dark-surface-deep min-h-[44px]"
    >
      <div className="mb-4 transition-transform duration-200 group-hover:scale-110">
        {icon}
      </div>
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
        {title}
      </h3>
      <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
        {description}
      </p>
    </div>
  );
};

export const WizardWelcome: React.FC<WizardWelcomeProps> = ({
  onSelectPath,
}) => {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-8 sm:py-12">
      <div className="w-full max-w-4xl">
        {/* Heading */}
        <div className="text-center mb-8 sm:mb-10">
          <h1 className="text-3xl sm:text-4xl font-bold text-brand-dark-blue dark:text-white mb-3">
            Let's get you funded
          </h1>
          <p className="text-base sm:text-lg text-gray-600 dark:text-gray-400 max-w-lg mx-auto leading-relaxed">
            We'll walk you through every step of the grant application process —
            from finding the right opportunity to building a professional
            proposal.
          </p>
        </div>

        {/* Path Selection Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6 mb-8">
          <PathCard
            icon={
              <Search className="w-10 h-10 text-brand-blue" strokeWidth={1.5} />
            }
            title="I have a grant in mind"
            description="I have a website link or document for a specific grant I want to apply for"
            onClick={() => onSelectPath("have_grant")}
          />
          <PathCard
            icon={
              <Lightbulb
                className="w-10 h-10 text-amber-500"
                strokeWidth={1.5}
              />
            }
            title="Help me find a grant"
            description="I need funding for my program and want to explore what's available"
            onClick={() => onSelectPath("find_grant")}
          />
          <PathCard
            icon={
              <FileEdit
                className="w-10 h-10 text-brand-green"
                strokeWidth={1.5}
              />
            }
            title="I just have an idea"
            description="No grant yet? Let's document your program, build a plan, and find matching grants"
            onClick={() => onSelectPath("build_program")}
          />
        </div>

        {/* Reassuring footer text */}
        <p className="text-center text-sm text-gray-500 dark:text-gray-400">
          Not sure? No problem — you can always change direction later.
        </p>
      </div>
    </div>
  );
};

export default WizardWelcome;
