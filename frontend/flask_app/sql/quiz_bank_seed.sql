-- EqWell quiz bank seed (4 quizzes, 120 questions)
-- Run this once on your SQLite database.

ALTER TABLE Questions ADD COLUMN polarity INT DEFAULT 1;

-- =========================
-- QUIZZES
-- =========================
INSERT INTO Quizzes (quiz_id, title, type, created_by) VALUES
(1, 'MindBalance Check', 'serious', 1),
(2, 'CalmPulse Assessment', 'serious', 1),
(3, 'StressLoad Analyzer', 'serious', 1),
(4, 'SocialConnect Index', 'serious', 1);

-- =========================
-- QUESTIONS (120 TOTAL)
-- =========================

INSERT INTO Questions (quiz_id, question_text, is_mandatory, weight, polarity) VALUES

-- =========================
-- MIND BALANCE (30)
-- =========================
(1,'How often do you feel genuinely happy in a day?',TRUE,3,1),
(1,'Do you find it easy to express your emotions?',FALSE,1,1),
(1,'How often do you feel sad without knowing why?',TRUE,3,-1),
(1,'Do you feel proud of your accomplishments?',TRUE,2,1),
(1,'How often do you feel emotionally drained?',TRUE,3,-1),
(1,'Do you feel hopeful about the future?',TRUE,2,1),
(1,'How often do you feel lonely even when around people?',TRUE,3,-1),
(1,'Do you feel in control of your emotions?',TRUE,2,1),
(1,'How often do you experience mood swings?',TRUE,2,-1),
(1,'Do you accept your flaws easily?',FALSE,1,1),
(1,'How often do you feel irritated or angry?',FALSE,2,-1),
(1,'Do you enjoy spending time with yourself?',FALSE,1,1),
(1,'Can you recognize when you are stressed before it escalates?',TRUE,2,1),
(1,'How often do you feel at peace with yourself?',TRUE,2,1),
(1,'Do you often overthink situations?',TRUE,3,-1),
(1,'Are you comfortable being vulnerable with others?',FALSE,1,1),
(1,'How often do you feel hopeful about the future?',TRUE,2,1),
(1,'Can you laugh at yourself without feeling bad?',FALSE,1,1),
(1,'Do you accept your flaws easily?',FALSE,1,1),
(1,'Are you able to let go of grudges quickly?',FALSE,1,1),
(1,'How often do you feel anxious about the opinions of others?',TRUE,2,-1),
(1,'Do you feel emotionally supported by friends or family?',TRUE,2,1),
(1,'How often do you feel restless?',FALSE,1,-1),
(1,'Can you stay calm in stressful situations?',TRUE,2,1),
(1,'Do you enjoy expressing your emotions through art, writing, or music?',FALSE,1,1),
(1,'How often do you feel emotionally drained?',TRUE,3,-1),
(1,'Do you feel a lack of motivation in daily activities?',TRUE,3,-1),
(1,'Do you feel emotionally numb at times?',TRUE,3,-1),
(1,'Do you feel disconnected from yourself?',TRUE,2,-1),
(1,'Do you feel satisfied with your life currently?',TRUE,2,1),

-- =========================
-- CALM PULSE (30)
-- =========================
(2,'How often do you feel anxious without a reason?',TRUE,3,-1),
(2,'How often do you feel overwhelmed by your thoughts?',TRUE,3,-1),
(2,'Can you easily identify your triggers for negative emotions?',TRUE,2,1),
(2,'How often do you feel stressed or anxious?',TRUE,3,-1),
(2,'Do you practice mindfulness regularly?',FALSE,2,1),
(2,'How often do you feel restless?',TRUE,2,-1),
(2,'Do you practice deep breathing or meditation?',FALSE,1,1),
(2,'How often do you feel anxious before major events?',TRUE,2,-1),
(2,'Can you recognize when you are stressed before it escalates?',TRUE,2,1),
(2,'How often do you overthink situations?',TRUE,3,-1),
(2,'How often do you feel pressure from expectations?',TRUE,2,-1),
(2,'Do you feel calm after exercising or physical activity?',FALSE,1,1),
(2,'How often do you worry about things you cannot control?',TRUE,3,-1),
(2,'Do you have relaxation routines before bed?',FALSE,1,1),
(2,'How often do you feel tension in your body?',TRUE,2,-1),
(2,'Do you feel confident in handling your emotions?',TRUE,2,1),
(2,'How often do you feel anxious about the future?',TRUE,2,-1),
(2,'Do you feel in control of your thoughts?',TRUE,2,1),
(2,'How often do you feel mentally exhausted?',TRUE,3,-1),
(2,'Do you find it easy to relax when needed?',TRUE,2,1),
(2,'How often do you feel panic in stressful situations?',TRUE,3,-1),
(2,'Do small problems feel overwhelming to you?',TRUE,3,-1),
(2,'Do you find it hard to relax even during free time?',TRUE,2,-1),
(2,'Do you feel your thoughts are racing frequently?',TRUE,2,-1),
(2,'Do you feel physically uneasy during stress?',TRUE,2,-1),
(2,'Do you use breathing techniques to calm yourself?',FALSE,1,1),
(2,'Do you feel safe in your environment?',TRUE,2,1),
(2,'Do you feel stable emotionally most days?',TRUE,2,1),
(2,'Do you struggle to stay present in the moment?',TRUE,2,-1),
(2,'Do you feel easily startled or tense?',TRUE,2,-1),

-- =========================
-- STRESS LOAD (30)
-- =========================
(3,'How often do you feel stressed at work or school?',TRUE,3,-1),
(3,'How often do you feel burnout?',TRUE,3,-1),
(3,'Do you have healthy coping mechanisms for stress?',TRUE,2,1),
(3,'How often do you feel pressured by deadlines?',TRUE,2,-1),
(3,'Are you able to sleep well when stressed?',TRUE,2,1),
(3,'How often do you procrastinate due to stress?',TRUE,2,-1),
(3,'Do you practice time management effectively?',TRUE,2,1),
(3,'How often do you feel tension in your body?',FALSE,2,-1),
(3,'Do you use hobbies as a stress outlet?',FALSE,1,1),
(3,'How often do you avoid tasks due to stress?',TRUE,2,-1),
(3,'Do you know your main sources of stress?',TRUE,2,1),
(3,'How often do you feel unable to cope with responsibilities?',TRUE,3,-1),
(3,'How often do you take breaks to relax?',FALSE,1,1),
(3,'How often do you feel stress impacting your health?',TRUE,3,-1),
(3,'Can you turn negative thoughts into positive actions?',TRUE,2,1),
(3,'Do you feel supported during stressful times?',TRUE,2,1),
(3,'Do you set realistic goals for yourself?',TRUE,2,1),
(3,'How often do you feel overwhelmed by social expectations?',TRUE,2,-1),
(3,'Do you feel confident in managing multiple responsibilities?',TRUE,2,1),
(3,'How often do you feel emotionally exhausted?',TRUE,3,-1),
(3,'Do you use journaling as a stress relief method?',FALSE,1,1),
(3,'Do you feel exhausted even after rest?',TRUE,3,-1),
(3,'Do you feel like you have too many responsibilities?',TRUE,2,-1),
(3,'Do you feel your workload is unmanageable?',TRUE,3,-1),
(3,'Do you feel drained at the end of the day?',TRUE,2,-1),
(3,'Do you take enough rest between tasks?',TRUE,2,1),
(3,'Do you feel productive most days?',TRUE,2,1),
(3,'Do you feel overwhelmed by deadlines frequently?',TRUE,2,-1),
(3,'Do you feel your efforts are recognized?',TRUE,2,1),
(3,'Do you feel in control of your workload?',TRUE,2,1),

-- =========================
-- SOCIAL CONNECT (30)
-- =========================
(4,'Do you feel supported by your friends?',TRUE,2,1),
(4,'How often do you feel lonely despite social connections?',TRUE,3,-1),
(4,'Do you find it easy to make new friends?',TRUE,2,1),
(4,'How often do you experience conflicts in relationships?',TRUE,2,-1),
(4,'Do you communicate your needs effectively?',TRUE,2,1),
(4,'How often do you feel judged by others?',TRUE,2,-1),
(4,'Do you invest time in nurturing relationships?',FALSE,1,1),
(4,'How often do you feel appreciated by others?',TRUE,2,1),
(4,'Are you able to maintain healthy boundaries?',TRUE,2,1),
(4,'How often do you experience empathy for others?',FALSE,1,1),
(4,'Do you feel comfortable opening up to others?',TRUE,2,1),
(4,'How often do you feel isolated?',TRUE,3,-1),
(4,'Do you trust people easily?',FALSE,1,1),
(4,'How often do you feel left out?',TRUE,2,-1),
(4,'Do you feel connected to your peers?',TRUE,2,1),
(4,'How often do you avoid social interactions?',TRUE,2,-1),
(4,'Do you feel heard when you speak?',TRUE,2,1),
(4,'Do you hesitate to reach out for help?',TRUE,2,-1),
(4,'Do you feel respected by others?',TRUE,2,1),
(4,'How often do you feel misunderstood?',TRUE,2,-1),
(4,'Do you feel comfortable in group settings?',TRUE,2,1),
(4,'Do you feel valued in your relationships?',TRUE,2,1),
(4,'Do you struggle to maintain friendships?',TRUE,2,-1),
(4,'Do you feel included in social groups?',TRUE,2,1),
(4,'Do you feel emotionally connected to others?',TRUE,2,1),
(4,'Do you feel people care about you?',TRUE,2,1),
(4,'Do you feel disconnected from people around you?',TRUE,3,-1),
(4,'Do you feel socially drained often?',TRUE,2,-1),
(4,'Do you feel confident in social situations?',TRUE,2,1),
(4,'Do you feel lonely even in groups?',TRUE,3,-1);
