package th.ac.mfu.repoai.config;

import java.util.List;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.AuthenticationSuccessHandler;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain securityFilterChain(
            HttpSecurity http,
            @Value("${app.frontend.url:https://repoai-frontend-516479753863.us-central1.run.app}") String frontendUrl,
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
    public AuthenticationSuccessHandler oauth2SuccessHandler(
            @Value("${app.frontend.url:https://repoai-frontend-516479753863.us-central1.run.app}") String frontendUrl) {
        return (request, response, authentication) -> {
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
            response.sendRedirect(redirect);
        };
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        // For local dev: allow any origin. For prod, restrict to known frontends.
        configuration.setAllowedOriginPatterns(List.of("*"));
        configuration.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(List.of("Authorization", "Content-Type", "X-Requested-With", "Accept"));
        configuration.setExposedHeaders(List.of("Location", "Link"));
        configuration.setAllowCredentials(true);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }
}
