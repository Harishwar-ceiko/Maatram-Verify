
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Brand } from "./ui";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="institution-auth">

      {/* Top information strip */}
      <div className="institution-top-strip">
        <div className="institution-container institution-strip-inner">
          <span>MAATRAM FOUNDATION</span>
          <span>EDUCATION · OPPORTUNITY · EMPOWERMENT</span>
          <span>ADMISSIONS 2026–27</span>
        </div>
      </div>

      {/* Institutional header */}
      <header className="institution-header">
        <div className="institution-container institution-header-inner">

          <Link to="/login" className="institution-brand">
  <img
    src="/maatram-logo.png"
    alt="Maatram Foundation"
    className="institution-brand-logo"
  />
  <span className="institution-brand-text">
    <span>STUDENT ADMISSION PORTAL</span>
    <strong>VERIFY</strong>
  </span>
</Link>

          <nav className="institution-header-nav">
            <a href="#about">About Us</a>
            <a href="#process">How It Works</a>
            <a href="#notices">Announcements</a>
          </nav>

          <a href="#student-login" className="institution-header-button">
            Applicant Login <span>↗</span>
          </a>

        </div>
      </header>

      <main>

        {/* Hero banner */}
        <section className="institution-hero" id="about">
          <div className="institution-container institution-hero-inner">

            <div className="institution-hero-copy">

              <div className="institution-eyebrow">
                <span />
                A STEP TOWARDS YOUR FUTURE
              </div>

              <h1>
                Education opens doors.
                <br />
                <em>Let opportunity lead the way.</em>
              </h1>

              <p>
                Maatram Foundation brings students and opportunities
                together through a transparent admission process.
                Submit your details, verify your documents and
                follow your application journey.
              </p>

              <div className="institution-hero-actions">
                <a href="#student-login" className="institution-yellow-button">
                  Access Student Portal <span>→</span>
                </a>

                <a href="#process" className="institution-outline-button">
                  Explore the process
                </a>
              </div>

              <div className="institution-hero-bottom">
                <span>01 / STUDENT APPLICATIONS</span>
                <span>02 / DOCUMENT VERIFICATION</span>
                <span>03 / REVIEW PROCESS</span>
              </div>
            </div>

            {/* Decorative institutional artwork */}
            <div className="institution-hero-art" aria-hidden="true">

              <div className="institution-art-circle">
                <div className="institution-art-inner">
                  <span>MV</span>
                  <strong>MAATRAM</strong>
                  <small>VERIFY</small>
                </div>
              </div>

              <div className="institution-art-card">
                <span>ADMISSIONS 2026–27</span>
                <strong>
                  One application.
                  <br />
                  A clearer path.
                </strong>
                <div className="institution-art-line" />
                <small>STUDENT SUPPORT INITIATIVE</small>
              </div>

              <div className="institution-art-number">01</div>

            </div>
          </div>
        </section>

        {/* Main information and login */}
        <section className="institution-container institution-content-grid">

          {/* Left information area */}
          <div className="institution-information" id="process">

            <div className="institution-section-heading">
              <span>YOUR ADMISSION JOURNEY</span>
              <h2>A simple process. A meaningful opportunity.</h2>
              <p>
                Every application follows a structured process
                designed to make document submission and verification
                easier to follow.
              </p>
            </div>

            <div className="institution-process-list">

              <div className="institution-process-item">
                <span className="institution-process-number">01</span>
                <div>
                  <h3>Submit your application</h3>
                  <p>
                    Enter your personal information and academic
                    details to create your admission application.
                  </p>
                </div>
              </div>

              <div className="institution-process-item">
                <span className="institution-process-number">02</span>
                <div>
                  <h3>Upload supporting documents</h3>
                  <p>
                    Attach your marksheets, identity documents
                    and other required certificates.
                  </p>
                </div>
              </div>

              <div className="institution-process-item">
                <span className="institution-process-number">03</span>
                <div>
                  <h3>Track document verification</h3>
                  <p>
                    Monitor document checks and view any
                    information that requires further review.
                  </p>
                </div>
              </div>

            </div>

            {/* Notice board */}
            <div className="institution-notice-board" id="notices">
              <div className="institution-notice-heading">
                <span>NOTICE BOARD</span>
                <span>ADMISSION INFORMATION</span>
              </div>

              <div className="institution-notice-content">
                <span className="institution-notice-marker">!</span>
                <div>
                  <strong>Important applicant information</strong>
                  <p>
                    Keep your academic records and supporting
                    documents ready before submitting an application.
                  </p>
                </div>
              </div>
            </div>

          </div>

          {/* Student login area */}
          <aside className="institution-login-area" id="student-login">

            <div className="institution-login-top">
              <div className="institution-login-icon">MV</div>

              <div>
                <span>STUDENT SERVICES</span>
                <strong>Applicant Portal</strong>
              </div>
            </div>

            <div className="institution-login-content">
              {children}
            </div>

            <div className="institution-login-bottom">
              <span>SECURE STUDENT ACCESS</span>
              <span>MAATRAM VERIFY · 2026–27</span>
            </div>

          </aside>

        </section>

      </main>

      {/* ABOUT MAATRAM - HOMEPAGE SECTIONS */}
      <div className="maatram-home-content">

        {/* TAMIL EDUCATION QUOTE */}
        <section className="maatram-quote-section">
          <div className="maatram-quote-inner">
            <p className="maatram-eyebrow">கல்வி • அறிவு • மாற்றம்</p>

            <h2 className="maatram-tamil-quote">
              கல்விக்கு முடிவே இல்லை.
              <br />
              ஒரு புத்தகத்தைப் படித்து, தேர்வில் தேர்ச்சி பெற்று,
              முடிப்பதல்ல கல்வி.
              <br />
              நீங்கள் பிறந்தது முதல் இறக்கும் வரை,
              முழு வாழ்க்கையும், ஒரு கற்றல் செயல்முறையே.
            </h2>

            <p className="maatram-quote-author">
              — ஜிட்டு கிருஷ்ணமூர்த்தி
            </p>
          </div>
        </section>

        {/* ABOUT MAATRAM */}
        <section className="maatram-about-section" id="about">
          <div className="maatram-about-heading">
            <span>01 / WHO WE ARE</span>
            <h2>About<br />Maatram<br />Foundation</h2>
            <p>மாற்றம் begins with opportunity.</p>
          </div>

          <div className="maatram-about-content">
            <h3>
              Every student deserves a chance to dream.
              Every dream deserves an opportunity.
            </h3>

            <p>
              A student's future should never be limited by their
              financial circumstances. Talent, determination and
              the desire to learn can be found everywhere, but
              opportunities are not always equally accessible.
            </p>

            <p>
              Maatram Foundation works towards bridging this gap
              by supporting deserving students from economically
              disadvantaged backgrounds in accessing higher
              education and building a better future.
            </p>

            <p>
              For Maatram, education is more than gaining admission
              to a college. It is about discovering potential,
              building confidence, developing independence and
              creating opportunities for the next generation.
            </p>
          </div>
        </section>

        {/* CORE SERVICE */}
        <section className="maatram-core-section">
          <div className="maatram-core-title">
            <span>02 / WHAT WE DO</span>
            <h2>Core<br />Service</h2>
            <p>Education that reaches those who need it most.</p>
          </div>

          <div className="maatram-core-content">
            <h3>Making higher education accessible.</h3>

            <p>
              Financial difficulties should not prevent a deserving
              student from pursuing higher education. Maatram
              works to connect eligible students with educational
              opportunities through institutional partnerships
              and student assistance.
            </p>

            <p>
              Support may extend beyond tuition to other essential
              educational needs, depending on the programme and
              applicable institutional arrangements.
            </p>

            <p>
              Through application assessment, document verification
              and personal interaction, the Foundation works to
              understand each student's educational needs and
              circumstances.
            </p>
          </div>
        </section>

        {/* BEYOND CLASSROOM */}
        <section className="maatram-beyond-section">
          <span>03 / BEYOND THE CLASSROOM</span>

          <h2>
            Learning does not end
            <br />
            with admission.
          </h2>

          <p className="maatram-beyond-lead">
            A college admission is the beginning of a new journey,
            not the destination.
          </p>

          <div className="maatram-beyond-grid">
            <article>
              <h3>01. Mentorship</h3>
              <p>
                Guidance and encouragement help students navigate
                their academic journey and face challenges with
                confidence.
              </p>
            </article>

            <article>
              <h3>02. Skill Development</h3>
              <p>
                Communication, leadership and practical skills
                prepare students for opportunities beyond academics.
              </p>
            </article>

            <article>
              <h3>03. Career Readiness</h3>
              <p>
                Employability preparation and technical learning
                help students move towards professional careers.
              </p>
            </article>

            <article>
              <h3>04. Continuous Learning</h3>
              <p>
                Learning, improvement and personal development
                remain important throughout a student's journey.
              </p>
            </article>
          </div>
        </section>

        {/* HOW THE PROCESS WORKS */}
        <section className="maatram-process-section">
          <span>04 / OUR APPROACH</span>
          <h2>Every application represents a future.</h2>

          <div className="maatram-process-grid">
            <article>
              <span>01</span>
              <h3>Application</h3>
              <p>
                Student information and supporting documents
                are collected for assessment.
              </p>
            </article>

            <article>
              <span>02</span>
              <h3>Verification</h3>
              <p>
                Academic records and submitted information
                are carefully reviewed.
              </p>
            </article>

            <article>
              <span>03</span>
              <h3>Assessment</h3>
              <p>
                Student circumstances and educational needs
                are considered during the review process.
              </p>
            </article>

            <article>
              <span>04</span>
              <h3>Opportunity</h3>
              <p>
                Eligible students may be considered for
                available educational support.
              </p>
            </article>
          </div>
        </section>

        {/* NEWS TO CHEER */}
        <section className="maatram-news-section">
          <div className="maatram-news-visual">
            <span>MAATRAM FOUNDATION</span>
            <h2>Every opportunity<br />can change a life.</h2>
          </div>

          <div className="maatram-news-content">
            <span>05 / NEWS TO CHEER</span>
            <h2>Dreams deserve<br />to move forward.</h2>

            <p>
              Behind every application is a student with ambitions,
              responsibilities and hopes for the future.
            </p>

            <p>
              Through education, guidance and collective effort,
              we can help make those ambitions possible.
            </p>

            <strong>
              One opportunity. One new beginning. Countless possibilities.
            </strong>
          </div>
        </section>

        {/* FINAL MESSAGE */}
        <section className="maatram-final-section">
          <p>மாற்றம் ஒரு வாய்ப்பில் தொடங்குகிறது.</p>

          <h2>
            Change begins when
            <br />
            someone gets an opportunity.
          </h2>

          <span>
            Supporting students. Creating opportunities. Transforming futures.
          </span>
        </section>

      </div>

      {/* Footer */}
      <footer className="institution-footer">
        <div className="institution-container institution-footer-inner">

          <div>
            <Brand size="sm" />
            <p>Supporting students. Creating opportunities.</p>
          </div>

          <div className="institution-footer-details">
            <span>MAATRAM FOUNDATION</span>
            <span>Student Admission & Document Verification</span>
            <span>© 2026 Maatram Verify</span>
          </div>

        </div>
      </footer>

    </div>
  );
}
