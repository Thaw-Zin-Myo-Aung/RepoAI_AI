package th.ac.mfu.repoai.config;

import java.util.List;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.AuthenticationSuccessHandler;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import th.ac.mfu.repoai.domain.User;
import th.ac.mfu.repoai.repository.UserRepository;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Value("${app.frontend.url:https://repoai-frontend-516479753863.us-central1.run.app}")
    private String frontendUrl;

    @Bean
    public SecurityFilterChain securityFilterChain(
        HttpSecurity http,
        AuthenticationSuccessHandler oauth2SuccessHandler) throws Exception {
        http
                .csrf(csrf -> csrf.disable())
                .cors(cors -> cors.configurationSource(corsConfigurationSource()))
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers(
                                "/api/auth/**",
                                "/api/**",
                                "/swagger-ui/**",
                                "/v3/api-docs/**",
                                "/swagger-resources/**",
                                "/webjars/**")
                        .permitAll() // adjust as needed
                        .anyRequest().authenticated())
                .oauth2Login(oauth2 -> oauth2
                        // Redirect to SPA after successful OAuth login
                        .successHandler(oauth2SuccessHandler))
                .logout(logout -> logout
            .logoutSuccessUrl(frontendUrl + "/login") // where to go after logout
                        .invalidateHttpSession(true)
                        .clearAuthentication(true));

        return http.build();
    }

    @Bean
    public AuthenticationSuccessHandler oauth2SuccessHandler(UserRepository userRepository) {
        return (request, response, authentication) -> {

      
            // Extract OAuth2 user info
            OAuth2User oauth2User = (OAuth2User) authentication.getPrincipal();
            
            // Get GitHub attributes
            Long githubId = ((Number) oauth2User.getAttribute("id")).longValue();
            String username = oauth2User.getAttribute("login");
            String email = oauth2User.getAttribute("email");
            String avatarUrl = oauth2User.getAttribute("avatar_url");
            String profileUrl = oauth2User.getAttribute("html_url");
            
            // Save or update user in database
            userRepository.findByGithubId(githubId).orElseGet(() -> {
                User newUser = new User();
                newUser.setGithubId(githubId);
                newUser.setUsername(username);
                newUser.setEmail(email);
                newUser.setAvatarUrl(avatarUrl);
                newUser.setProfileUrl(profileUrl);
                return userRepository.save(newUser);
            });


            String redirect = null;
            var cookies = request.getCookies();
            if (cookies != null) {
                for (var c : cookies) {
                    if ("app_redirect".equals(c.getName())) {
                        redirect = java.net.URLDecoder.decode(
                                c.getValue(), java.nio.charset.StandardCharsets.UTF_8);
                        // clear cookie
                        c.setMaxAge(0);
                        c.setPath("/");
                        response.addCookie(c);
                        break;
                    }
                }
            }
            if (redirect == null || redirect.isBlank()) {
                redirect = frontendUrl + "/home"; // fallback
            }
            // Ensure longer session inactivity window (align with application.properties: 2 days)
            request.getSession().setMaxInactiveInterval(2 * 24 * 60 * 60); // seconds
            response.sendRedirect(redirect);
        };
        }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        // Allow the configured frontend origin and common local dev origins
        configuration.setAllowedOriginPatterns(List.of(
            frontendUrl,
            "http://localhost:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174"
        ));
        configuration.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(List.of("Authorization", "Content-Type", "X-Requested-With", "Accept"));
        configuration.setExposedHeaders(List.of("Location", "Link"));
        configuration.setAllowCredentials(true);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }
}
