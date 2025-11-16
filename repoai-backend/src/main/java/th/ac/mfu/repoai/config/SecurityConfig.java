package th.ac.mfu.repoai.config;

import java.io.IOException;
import java.util.List;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.AuthenticationSuccessHandler;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

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
                        .permitAll()
                        .anyRequest().authenticated())
                .oauth2Login(oauth2 -> oauth2
                        .successHandler(oauth2SuccessHandler))
                .logout(logout -> logout
                        .logoutSuccessUrl("https://repoai-frontend-516479753863.us-central1.run.app/login")
                        .invalidateHttpSession(true)
                        .clearAuthentication(true));

        return http.build();
    }

    @Bean
    public AuthenticationSuccessHandler oauth2SuccessHandler() {
        return new AuthenticationSuccessHandler() {
            @Override
            public void onAuthenticationSuccess(HttpServletRequest request,
                    HttpServletResponse response,
                    Authentication authentication) throws IOException, ServletException {

                // ALWAYS redirect to frontend - no cookie logic needed
                String frontendUrl = "https://repoai-frontend-516479753863.us-central1.run.app";
                String redirectUrl = frontendUrl + "/home";

                System.out.println("=== OAuth Success Handler ===");
                System.out.println("Redirecting to: " + redirectUrl);

                // Get user info for debugging
                if (authentication.getPrincipal() instanceof OAuth2User) {
                    OAuth2User oauth2User = (OAuth2User) authentication.getPrincipal();
                    String username = oauth2User.getAttribute("login");
                    System.out.println("User logged in: " + username);
                }

                response.sendRedirect(redirectUrl);
            }
        };
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        // Allow specific origins for production
        configuration.setAllowedOrigins(List.of(
                "https://repoai-frontend-516479753863.us-central1.run.app",
                "http://localhost:5173",
                "http://localhost:3000"));
        configuration.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(List.of("Authorization", "Content-Type", "X-Requested-With", "Accept"));
        configuration.setExposedHeaders(List.of("Location", "Link"));
        configuration.setAllowCredentials(true);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }
}